"""
ARIA / SAKHI — Emergency Service
==================================
BE3 OWNS THIS FILE.

Core incident lifecycle operations:
  - create_incident (SOS + AI trigger)
  - get_incident / list_incidents
  - cancel_incident
  - resolve_incident
  - log_event (timeline)
"""

import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.emergency import (
    EmergencyIncident,
    IncidentEvent,
    IncidentLocationUpdate,
)
from app.schemas.emergency import (
    AITriggerRequest,
    EmergencyIncidentRead,
    EmergencyIncidentWithTimeline,
    SOSRequest,
)
from fastapi import HTTPException, status


# ─── Helpers ──────────────────────────────────────────────────────────────────

async def log_event(
    db: AsyncSession,
    incident_id: uuid.UUID,
    event_type: str,
    description: str,
    metadata: dict[str, Any] | None = None,
) -> IncidentEvent:
    """Append an immutable timeline event to an incident."""
    event = IncidentEvent(
        incident_id=incident_id,
        event_type=event_type,
        description=description,
        metadata=metadata,
    )
    db.add(event)
    await db.flush()
    return event


async def _get_incident_or_404(
    incident_id: uuid.UUID,
    db: AsyncSession,
) -> EmergencyIncident:
    result = await db.execute(
        select(EmergencyIncident).where(EmergencyIncident.id == incident_id)
    )
    incident = result.scalar_one_or_none()
    if incident is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Incident {incident_id} not found.",
        )
    return incident


def _assert_owner(incident: EmergencyIncident, user_id: uuid.UUID) -> None:
    """Raise 403 if the requesting user does not own the incident."""
    if incident.user_id != user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You are not authorized to access this incident.",
        )


def _assert_active(incident: EmergencyIncident) -> None:
    """Raise 409 if the incident is no longer active."""
    if not incident.is_active:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Incident is already {incident.status} and cannot be modified.",
        )


# ─── Create ───────────────────────────────────────────────────────────────────

async def create_manual_sos(
    user_id: uuid.UUID,
    payload: SOSRequest,
    db: AsyncSession,
    policy_snapshot: dict[str, Any] | None = None,
) -> EmergencyIncident:
    """
    Create an emergency incident from a manual SOS trigger.
    Manual SOS is always CRITICAL risk regardless of AI score.
    """
    incident = EmergencyIncident(
        user_id=user_id,
        trigger_type="MANUAL_SOS",
        status="ACTIVE",
        risk_level="CRITICAL",
        risk_score=None,
        latitude=payload.latitude,
        longitude=payload.longitude,
        location_accuracy=payload.accuracy,
        location_updated_at=datetime.now(timezone.utc) if payload.latitude else None,
        policy_snapshot=policy_snapshot,
    )
    db.add(incident)
    await db.flush()  # get the id

    await log_event(
        db,
        incident.id,
        "INCIDENT_CREATED",
        "Emergency incident created via manual SOS.",
        {"trigger": "MANUAL_SOS", "has_location": payload.latitude is not None},
    )

    return incident


async def create_ai_triggered_incident(
    payload: AITriggerRequest,
    db: AsyncSession,
    policy_snapshot: dict[str, Any] | None = None,
) -> EmergencyIncident:
    """
    Create an emergency incident from an AI risk result (from BE1).
    Starts in VERIFYING status to allow user confirmation.
    """
    incident = EmergencyIncident(
        user_id=payload.user_id,
        trigger_type=payload.trigger_type,
        status="VERIFYING",  # AI triggers go through verification first
        risk_level=payload.risk_level,
        risk_score=payload.risk_score,
        latitude=payload.latitude,
        longitude=payload.longitude,
        ai_reasons=payload.reasons,
        policy_snapshot=policy_snapshot,
        location_updated_at=(
            datetime.now(timezone.utc) if payload.latitude else None
        ),
    )
    db.add(incident)
    await db.flush()

    await log_event(
        db,
        incident.id,
        "AI_TRIGGER_RECEIVED",
        f"AI risk result received. Score: {payload.risk_score}, Level: {payload.risk_level}.",
        {
            "risk_score": payload.risk_score,
            "risk_level": payload.risk_level,
            "reasons": payload.reasons,
            "trigger_type": payload.trigger_type,
        },
    )

    return incident


# ─── Read ─────────────────────────────────────────────────────────────────────

async def get_incident(
    incident_id: uuid.UUID,
    user_id: uuid.UUID,
    db: AsyncSession,
) -> EmergencyIncident:
    """Return an incident the requesting user owns."""
    incident = await _get_incident_or_404(incident_id, db)
    _assert_owner(incident, user_id)
    return incident


async def get_incident_with_timeline(
    incident_id: uuid.UUID,
    user_id: uuid.UUID,
    db: AsyncSession,
) -> EmergencyIncident:
    """Return an incident with eagerly loaded events."""
    result = await db.execute(
        select(EmergencyIncident)
        .where(EmergencyIncident.id == incident_id)
        .options(selectinload(EmergencyIncident.events))
    )
    incident = result.scalar_one_or_none()
    if incident is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Incident {incident_id} not found.",
        )
    _assert_owner(incident, user_id)
    return incident


async def list_user_incidents(
    user_id: uuid.UUID,
    db: AsyncSession,
    limit: int = 20,
    offset: int = 0,
) -> list[EmergencyIncident]:
    """List all incidents for the authenticated user, newest first."""
    result = await db.execute(
        select(EmergencyIncident)
        .where(EmergencyIncident.user_id == user_id)
        .order_by(EmergencyIncident.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    return list(result.scalars().all())


# ─── Mutations ────────────────────────────────────────────────────────────────

async def cancel_incident(
    incident_id: uuid.UUID,
    user_id: uuid.UUID,
    db: AsyncSession,
) -> EmergencyIncident:
    """User cancels their own active incident."""
    incident = await _get_incident_or_404(incident_id, db)
    _assert_owner(incident, user_id)
    _assert_active(incident)

    incident.status = "CANCELLED"
    incident.resolved_at = datetime.now(timezone.utc)
    db.add(incident)

    await log_event(
        db,
        incident.id,
        "INCIDENT_CANCELLED",
        "Incident cancelled by the user.",
    )

    return incident


async def resolve_incident(
    incident_id: uuid.UUID,
    user_id: uuid.UUID,
    db: AsyncSession,
    resolved_by: str = "USER",
) -> EmergencyIncident:
    """Mark an incident as resolved."""
    incident = await _get_incident_or_404(incident_id, db)
    _assert_owner(incident, user_id)

    if incident.status == "RESOLVED":
        return incident  # idempotent

    incident.status = "RESOLVED"
    incident.resolved_at = datetime.now(timezone.utc)
    db.add(incident)

    await log_event(
        db,
        incident.id,
        "INCIDENT_RESOLVED",
        f"Incident resolved. Resolved by: {resolved_by}.",
        {"resolved_by": resolved_by},
    )

    return incident


async def update_incident_status(
    incident: EmergencyIncident,
    new_status: str,
    db: AsyncSession,
) -> EmergencyIncident:
    """Internal — update incident status without ownership check (for escalation engine)."""
    incident.status = new_status
    db.add(incident)
    await db.flush()
    return incident


async def update_incident_location(
    incident: EmergencyIncident,
    latitude: float,
    longitude: float,
    accuracy: float | None,
    db: AsyncSession,
) -> EmergencyIncident:
    """Update the latest location on the incident and persist a location history record."""
    now = datetime.now(timezone.utc)
    incident.latitude = latitude
    incident.longitude = longitude
    incident.location_accuracy = accuracy
    incident.location_updated_at = now
    db.add(incident)

    location_record = IncidentLocationUpdate(
        incident_id=incident.id,
        latitude=latitude,
        longitude=longitude,
        accuracy=accuracy,
    )
    db.add(location_record)
    await db.flush()

    return incident


async def get_active_incident_for_user(
    user_id: uuid.UUID,
    db: AsyncSession,
) -> EmergencyIncident | None:
    """Return the user's most recent active incident, or None."""
    result = await db.execute(
        select(EmergencyIncident)
        .where(
            EmergencyIncident.user_id == user_id,
            EmergencyIncident.status.in_(["ACTIVE", "VERIFYING", "ESCALATING"]),
        )
        .order_by(EmergencyIncident.created_at.desc())
        .limit(1)
    )
    return result.scalar_one_or_none()
