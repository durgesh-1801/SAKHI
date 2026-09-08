"""
ARIA / SAKHI — Verification Service
=====================================
BE3 OWNS THIS FILE.

Handles the "Are you safe?" verification stage:
  - request_verification: transition incident to VERIFYING, schedule timeout task
  - handle_verification_response: USER_CONFIRMED_SAFE or USER_REQUESTED_HELP
"""

from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.emergency import EmergencyIncident
from app.models.policy import EmergencyPolicy
from app.schemas.user import UserRead
from app.services.emergency_service import log_event, update_incident_status


async def request_verification(
    incident: EmergencyIncident,
    policy: EmergencyPolicy,
    db: AsyncSession,
) -> EmergencyIncident:
    """
    Transition an incident to VERIFYING and schedule the no-response Celery task.

    The timeout comes from the user's configured policy — never hard-coded.
    The Celery task ID is stored on the incident so it can be revoked
    if the user responds before the timeout.
    """
    incident = await update_incident_status(incident, "VERIFYING", db)

    timeout = policy.verification_timeout_seconds

    # Schedule the background no-response handler
    from app.tasks.escalation_tasks import handle_no_response_task

    task = handle_no_response_task.apply_async(
        args=[str(incident.id)],
        countdown=timeout,
    )

    # Store the task ID so we can revoke it on user response
    incident.escalation_task_id = task.id
    db.add(incident)
    await db.flush()

    await log_event(
        db,
        incident.id,
        "VERIFICATION_REQUESTED",
        f"Verification requested. User has {timeout}s to respond.",
        {
            "timeout_seconds": timeout,
            "celery_task_id": task.id,
        },
    )

    # Push "Are you safe?" notification to user
    from app.services.notifications.dispatcher import notification_dispatcher

    expires_at = datetime.now(UTC).timestamp() + timeout
    await notification_dispatcher.send_verification_request(
        user_id=incident.user_id,
        incident_id=str(incident.id),
        timeout_seconds=timeout,
        expires_at=datetime.fromtimestamp(expires_at, tz=UTC).isoformat(),
    )

    # Push WS event to user's own connection
    from app.websocket.manager import ws_manager

    await ws_manager.broadcast_to_incident(
        str(incident.id),
        {
            "event": "verification_request",
            "incident_id": str(incident.id),
            "message": "Are you safe? Please respond.",
            "expires_at": datetime.fromtimestamp(expires_at, tz=UTC).isoformat(),
        },
    )

    return incident


async def handle_verification_response(
    incident: EmergencyIncident,
    response: str,
    user: UserRead,
    db: AsyncSession,
) -> EmergencyIncident:
    """
    Process the user's response to verification.

    USER_CONFIRMED_SAFE → cancel timeout task, cancel incident.
    USER_REQUESTED_HELP → cancel timeout task, escalate immediately.
    """
    if incident.status != "VERIFYING":
        from fastapi import HTTPException, status

        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Cannot verify incident in status '{incident.status}'. Verification is only valid for incidents in 'VERIFYING' status.",
        )

    # Revoke the pending Celery timeout task if it exists
    if incident.escalation_task_id:
        _revoke_escalation_task(incident.escalation_task_id)
        incident.escalation_task_id = None
        db.add(incident)

    if response == "USER_CONFIRMED_SAFE":
        incident = await update_incident_status(incident, "CANCELLED", db)
        incident.resolved_at = datetime.now(UTC)
        db.add(incident)

        await log_event(
            db,
            incident.id,
            "USER_CONFIRMED_SAFE",
            "User confirmed they are safe. Incident cancelled.",
        )

        from app.websocket.manager import ws_manager

        await ws_manager.broadcast_to_incident(
            str(incident.id),
            {
                "event": "incident_resolved",
                "incident_id": str(incident.id),
                "status": "CANCELLED",
                "resolved_by": "USER_CONFIRMED_SAFE",
                "timestamp": datetime.now(UTC).isoformat(),
            },
        )

    elif response == "USER_REQUESTED_HELP":
        await log_event(
            db,
            incident.id,
            "USER_REQUESTED_HELP",
            "User explicitly requested help. Starting immediate escalation.",
        )
        from app.services.escalation_service import execute_escalation
        from app.services.policy_service import get_policy_or_default

        policy = await get_policy_or_default(incident.user_id, db)
        incident = await execute_escalation(
            incident=incident,
            user=user,
            policy=policy,
            db=db,
        )

    return incident


def _revoke_escalation_task(task_id: str) -> None:
    """Revoke a Celery task by ID (best-effort — does not raise if already done)."""
    try:
        from app.tasks.celery_app import celery_app

        celery_app.control.revoke(task_id, terminate=True, signal="SIGTERM")
    except Exception:  # noqa: BLE001
        pass  # Task may have already completed — safe to ignore
