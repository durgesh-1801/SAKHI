"""
ARIA / SAKHI — Emergency Router
=================================
BE3 OWNS THIS FILE.

HTTP endpoints:
  POST   /emergency/sos                          Manual SOS trigger
  POST   /emergency/trigger                      AI-triggered incident (BE1 internal)
  GET    /emergency/incidents                    List user's incidents
  GET    /emergency/incidents/{id}               Incident detail
  GET    /emergency/incidents/{id}/timeline      Full event timeline
  POST   /emergency/incidents/{id}/verify        Verification response
  POST   /emergency/incidents/{id}/cancel        Cancel incident
  POST   /emergency/incidents/{id}/resolve       Resolve incident
  GET    /emergency/incidents/{id}/location      Latest location (guardian-only)

WebSocket endpoint:
  WS     /ws/emergency/{incident_id}             Real-time guardian channel
"""

import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, Request, WebSocket, status
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import get_current_user
from app.database import get_db
from app.schemas.emergency import (
    AITriggerRequest,
    EmergencyIncidentRead,
    EmergencyIncidentWithTimeline,
    LocationResponse,
    SOSRequest,
    SOSResponse,
    VerifyRequest,
    VerifyResponse,
)
from app.schemas.user import UserRead
from app.services import (
    consent_service,
    contact_service,
    emergency_service,
    escalation_service,
    verification_service,
)
from app.websocket.manager import ws_manager

router = APIRouter()
ws_router = APIRouter()

# ─── Rate limiting (applied at app level via slowapi) ─────────────────────────
# SOS is limited to SOS_RATE_LIMIT_PER_MINUTE per user (configured in main.py)


# ──────────────────────────────────────────────────────────────────────────────
# POST /emergency/sos
# ──────────────────────────────────────────────────────────────────────────────


@router.post(
    "/sos",
    response_model=SOSResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Trigger a manual SOS emergency",
    description=(
        "Creates an emergency incident immediately. "
        "Reads the user's emergency policy and starts escalation. "
        "Rate-limited to prevent accidental spam."
    ),
)
async def trigger_sos(
    request: Request,
    payload: SOSRequest,
    current_user: UserRead = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> SOSResponse:
    from app.services.policy_service import get_policy_or_default

    policy = await get_policy_or_default(current_user.id, db)
    policy_snapshot = {
        "verification_timeout_seconds": policy.verification_timeout_seconds,
        "auto_escalate": policy.auto_escalate,
        "notify_primary_on_no_response": policy.notify_primary_on_no_response,
        "notify_secondary_on_no_response": policy.notify_secondary_on_no_response,
        "share_location_on_escalation": policy.share_location_on_escalation,
    }

    incident = await emergency_service.create_manual_sos(
        user_id=current_user.id,
        payload=payload,
        db=db,
        policy_snapshot=policy_snapshot,
    )
    await db.flush()

    # Start escalation pipeline (non-blocking — schedules Celery tasks)
    await escalation_service.start_escalation(
        incident=incident,
        user=current_user,
        policy=policy,
        db=db,
    )

    await db.commit()

    return SOSResponse(
        incident_id=incident.id,
        status=incident.status,
        risk_level=incident.risk_level,
    )


# ──────────────────────────────────────────────────────────────────────────────
# POST /emergency/trigger  (BE1 integration point)
# ──────────────────────────────────────────────────────────────────────────────


@router.post(
    "/trigger",
    response_model=SOSResponse,
    status_code=status.HTTP_201_CREATED,
    summary="AI-triggered emergency (BE1 internal)",
    description=(
        "Called by Backend Engineer 1's AI/risk engine. "
        "Creates an incident if the user has consented to AI monitoring. "
        "Starts in VERIFYING status — sends 'Are you safe?' before escalating."
    ),
)
async def trigger_from_ai(
    payload: AITriggerRequest,
    current_user: UserRead = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> SOSResponse:
    """
    BE1 INTEGRATION POINT
    ----------------------
    BE1's risk engine calls this endpoint with a risk result payload.
    The `current_user` is authenticated as BE1's service account or
    the user themselves (depending on BE1's architecture).

    If called as the user:
        payload.user_id must equal current_user.id (enforced below).
    If called as a service account:
        BE1 must pass the target user_id in the payload.
        BE1 should coordinate with BE3 on service-account auth.
    """
    # Consent gate — do not act on AI result without user's consent
    can_act = await consent_service.can_act_on_ai_result(payload.user_id, db)
    if not can_act:
        # Log that we denied but don't create an incident
        return JSONResponse(  # type: ignore[return-value]
            status_code=status.HTTP_200_OK,
            content={
                "detail": "AI trigger received but user has not consented to AI monitoring.",
                "user_id": str(payload.user_id),
            },
        )

    from app.services.policy_service import get_policy_or_default

    policy = await get_policy_or_default(payload.user_id, db)
    policy_snapshot = {
        "verification_timeout_seconds": policy.verification_timeout_seconds,
        "auto_escalate": policy.auto_escalate,
        "notify_primary_on_no_response": policy.notify_primary_on_no_response,
        "notify_secondary_on_no_response": policy.notify_secondary_on_no_response,
        "share_location_on_escalation": policy.share_location_on_escalation,
    }

    incident = await emergency_service.create_ai_triggered_incident(
        payload=payload,
        db=db,
        policy_snapshot=policy_snapshot,
    )

    # Start escalation — will send verification first, then escalate on no response
    await escalation_service.start_escalation(
        incident=incident,
        user=current_user,
        policy=policy,
        db=db,
    )

    await db.commit()

    return SOSResponse(
        incident_id=incident.id,
        status=incident.status,
        risk_level=incident.risk_level,
        message=(
            "AI-triggered incident created. Verification request sent. "
            f"Escalation in {policy.verification_timeout_seconds}s if no response."
        ),
    )


# ──────────────────────────────────────────────────────────────────────────────
# GET /emergency/incidents
# ──────────────────────────────────────────────────────────────────────────────


@router.get(
    "/incidents",
    response_model=list[EmergencyIncidentRead],
    summary="List user's emergency incidents",
)
async def list_incidents(
    limit: int = 20,
    offset: int = 0,
    current_user: UserRead = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[EmergencyIncidentRead]:
    incidents = await emergency_service.list_user_incidents(
        user_id=current_user.id, db=db, limit=min(limit, 100), offset=offset
    )
    return [EmergencyIncidentRead.model_validate(i) for i in incidents]


# ──────────────────────────────────────────────────────────────────────────────
# GET /emergency/incidents/{incident_id}
# ──────────────────────────────────────────────────────────────────────────────


@router.get(
    "/incidents/{incident_id}",
    response_model=EmergencyIncidentRead,
    summary="Get incident detail",
)
async def get_incident(
    incident_id: uuid.UUID,
    current_user: UserRead = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> EmergencyIncidentRead:
    incident = await emergency_service.get_incident(
        incident_id=incident_id, user_id=current_user.id, db=db
    )
    return EmergencyIncidentRead.model_validate(incident)


# ──────────────────────────────────────────────────────────────────────────────
# GET /emergency/incidents/{incident_id}/timeline
# ──────────────────────────────────────────────────────────────────────────────


@router.get(
    "/incidents/{incident_id}/timeline",
    response_model=EmergencyIncidentWithTimeline,
    summary="Get incident with full event timeline",
)
async def get_incident_timeline(
    incident_id: uuid.UUID,
    current_user: UserRead = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> EmergencyIncidentWithTimeline:
    incident = await emergency_service.get_incident_with_timeline(
        incident_id=incident_id, user_id=current_user.id, db=db
    )
    return EmergencyIncidentWithTimeline.model_validate(incident)


# ──────────────────────────────────────────────────────────────────────────────
# POST /emergency/incidents/{incident_id}/verify
# ──────────────────────────────────────────────────────────────────────────────


@router.post(
    "/incidents/{incident_id}/verify",
    response_model=VerifyResponse,
    summary="Respond to the 'Are you safe?' verification",
    description=(
        "USER_CONFIRMED_SAFE → cancels escalation timeout, resolves incident.\n"
        "USER_REQUESTED_HELP → immediately starts escalation."
    ),
)
async def verify_incident(
    incident_id: uuid.UUID,
    payload: VerifyRequest,
    current_user: UserRead = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> VerifyResponse:
    incident = await emergency_service.get_incident(
        incident_id=incident_id, user_id=current_user.id, db=db
    )

    updated_incident = await verification_service.handle_verification_response(
        incident=incident,
        response=payload.response,
        user=current_user,
        db=db,
    )
    await db.commit()

    message_map = {
        "USER_CONFIRMED_SAFE": "You've confirmed you are safe. Incident cancelled.",
        "USER_REQUESTED_HELP": "Help requested. Notifying your emergency contacts now.",
    }

    return VerifyResponse(
        incident_id=updated_incident.id,
        status=updated_incident.status,
        message=message_map.get(payload.response, "Response recorded."),
    )


# ──────────────────────────────────────────────────────────────────────────────
# POST /emergency/incidents/{incident_id}/cancel
# ──────────────────────────────────────────────────────────────────────────────


@router.post(
    "/incidents/{incident_id}/cancel",
    response_model=VerifyResponse,
    summary="Cancel an active incident",
)
async def cancel_incident(
    incident_id: uuid.UUID,
    current_user: UserRead = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> VerifyResponse:
    incident = await emergency_service.cancel_incident(
        incident_id=incident_id, user_id=current_user.id, db=db
    )
    await db.commit()

    # Broadcast cancellation to all WebSocket subscribers
    await ws_manager.broadcast_to_incident(
        str(incident_id),
        {
            "event": "incident_resolved",
            "incident_id": str(incident_id),
            "status": "CANCELLED",
            "resolved_by": "USER",
            "timestamp": datetime.now(UTC).isoformat(),
        },
    )

    return VerifyResponse(
        incident_id=incident.id,
        status=incident.status,
        message="Incident cancelled.",
    )


# ──────────────────────────────────────────────────────────────────────────────
# POST /emergency/incidents/{incident_id}/resolve
# ──────────────────────────────────────────────────────────────────────────────


@router.post(
    "/incidents/{incident_id}/resolve",
    response_model=VerifyResponse,
    summary="Mark incident as resolved",
)
async def resolve_incident(
    incident_id: uuid.UUID,
    current_user: UserRead = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> VerifyResponse:
    incident = await emergency_service.resolve_incident(
        incident_id=incident_id, user_id=current_user.id, db=db
    )
    await db.commit()

    await ws_manager.broadcast_to_incident(
        str(incident_id),
        {
            "event": "incident_resolved",
            "incident_id": str(incident_id),
            "status": "RESOLVED",
            "resolved_by": "USER",
            "timestamp": datetime.now(UTC).isoformat(),
        },
    )

    return VerifyResponse(
        incident_id=incident.id,
        status=incident.status,
        message="Incident resolved.",
    )


# ──────────────────────────────────────────────────────────────────────────────
# GET /emergency/incidents/{incident_id}/location
# Guardian-only endpoint — no public access
# ──────────────────────────────────────────────────────────────────────────────


@router.get(
    "/incidents/{incident_id}/location",
    response_model=LocationResponse,
    summary="Get latest location for an incident (guardian/trusted contact only)",
    description=(
        "Only accessible by the incident owner OR a trusted contact of the owner. "
        "Returns the latest known location updated during the incident."
    ),
)
async def get_incident_location(
    incident_id: uuid.UUID,
    current_user: UserRead = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> LocationResponse:
    from sqlalchemy import select

    from app.models.emergency import EmergencyIncident

    result = await db.execute(select(EmergencyIncident).where(EmergencyIncident.id == incident_id))
    incident = result.scalar_one_or_none()
    if incident is None:
        from fastapi import HTTPException

        raise HTTPException(status_code=404, detail="Incident not found.")

    # Authorization: must be owner OR trusted contact of owner
    is_owner = incident.user_id == current_user.id
    is_guardian = await contact_service.is_trusted_contact(
        guardian_user_id=current_user.id,
        incident_user_id=incident.user_id,
        db=db,
    )

    if not (is_owner or is_guardian):
        from fastapi import HTTPException

        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You are not authorized to view this incident's location.",
        )

    # Only expose location for active incidents
    if not incident.is_active and incident.latitude is None:
        from fastapi import HTTPException

        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No location data available for this incident.",
        )

    return LocationResponse(
        incident_id=incident.id,
        latitude=incident.latitude,
        longitude=incident.longitude,
        location_accuracy=incident.location_accuracy,
        location_updated_at=incident.location_updated_at,
        status=incident.status,
    )


# ──────────────────────────────────────────────────────────────────────────────
# WS /ws/emergency/{incident_id}
# Real-time guardian channel
# ──────────────────────────────────────────────────────────────────────────────


@ws_router.websocket("/ws/emergency/{incident_id}")
async def emergency_websocket(
    websocket: WebSocket,
    incident_id: str,
    token: str,  # query param: wss://host/ws/emergency/ID?token=JWT
    db: AsyncSession = Depends(get_db),
) -> None:
    """
    Real-time WebSocket channel for an emergency incident.

    Auth: Bearer token passed as query param `token`.
    Authorization: Must be incident owner or trusted contact.

    Server → Client events:
        location_update, incident_update, verification_request,
        contact_notified, incident_resolved, error

    Client → Server events:
        location_update (from mobile app during emergency)
        ping
    """
    from app.websocket.handlers import handle_websocket_connection

    await handle_websocket_connection(
        websocket=websocket,
        incident_id=incident_id,
        token=token,
        db=db,
    )
