"""
ARIA / SAKHI — Emergency Domain Models
========================================
BE3 OWNS THIS FILE.

Tables:
  - emergency_incidents      — core incident record
  - incident_events          — immutable timeline log for each incident
  - incident_location_updates — every location ping during an active incident
"""

from __future__ import annotations

import uuid
from datetime import datetime
from enum import Enum as PyEnum
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from app.models.user import User

from sqlalchemy import (
    JSON,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Index,
    String,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import GUID, Base

# ─── Enumerations ──────────────────────────────────────────────────────────────


class RiskLevel(str, PyEnum):
    SAFE = "SAFE"
    SUSPICIOUS = "SUSPICIOUS"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class IncidentStatus(str, PyEnum):
    ACTIVE = "ACTIVE"
    VERIFYING = "VERIFYING"
    ESCALATING = "ESCALATING"
    RESOLVED = "RESOLVED"
    CANCELLED = "CANCELLED"


class TriggerType(str, PyEnum):
    MANUAL_SOS = "MANUAL_SOS"
    AI_DETECTION = "AI_DETECTION"
    FALL_DETECTION = "FALL_DETECTION"
    DISTRESS_DETECTION = "DISTRESS_DETECTION"
    SAFE_JOURNEY = "SAFE_JOURNEY"
    OTHER = "OTHER"


class VerificationResponse(str, PyEnum):
    USER_CONFIRMED_SAFE = "USER_CONFIRMED_SAFE"
    USER_REQUESTED_HELP = "USER_REQUESTED_HELP"
    NO_RESPONSE = "NO_RESPONSE"


class EventType(str, PyEnum):
    INCIDENT_CREATED = "INCIDENT_CREATED"
    VERIFICATION_REQUESTED = "VERIFICATION_REQUESTED"
    USER_CONFIRMED_SAFE = "USER_CONFIRMED_SAFE"
    USER_REQUESTED_HELP = "USER_REQUESTED_HELP"
    NO_RESPONSE = "NO_RESPONSE"
    CONTACT_NOTIFIED = "CONTACT_NOTIFIED"
    LOCATION_SHARING_STARTED = "LOCATION_SHARING_STARTED"
    LOCATION_UPDATED = "LOCATION_UPDATED"
    ESCALATED = "ESCALATED"
    INCIDENT_RESOLVED = "INCIDENT_RESOLVED"
    INCIDENT_CANCELLED = "INCIDENT_CANCELLED"
    AI_TRIGGER_RECEIVED = "AI_TRIGGER_RECEIVED"
    CONSENT_DENIED = "CONSENT_DENIED"


# ─── SQLAlchemy Enum types (reusable) ─────────────────────────────────────────

risk_level_enum = Enum(
    "SAFE",
    "SUSPICIOUS",
    "HIGH",
    "CRITICAL",
    name="risk_level_enum",
)

incident_status_enum = Enum(
    "ACTIVE",
    "VERIFYING",
    "ESCALATING",
    "RESOLVED",
    "CANCELLED",
    name="incident_status_enum",
)

trigger_type_enum = Enum(
    "MANUAL_SOS",
    "AI_DETECTION",
    "FALL_DETECTION",
    "DISTRESS_DETECTION",
    "SAFE_JOURNEY",
    "OTHER",
    name="trigger_type_enum",
)

event_type_enum = Enum(
    "INCIDENT_CREATED",
    "VERIFICATION_REQUESTED",
    "USER_CONFIRMED_SAFE",
    "USER_REQUESTED_HELP",
    "NO_RESPONSE",
    "CONTACT_NOTIFIED",
    "LOCATION_SHARING_STARTED",
    "LOCATION_UPDATED",
    "ESCALATED",
    "INCIDENT_RESOLVED",
    "INCIDENT_CANCELLED",
    "AI_TRIGGER_RECEIVED",
    "CONSENT_DENIED",
    name="event_type_enum",
)


# ─── Models ───────────────────────────────────────────────────────────────────


class EmergencyIncident(Base):
    """
    Core emergency incident record.

    Lifecycle:
        MANUAL_SOS → ACTIVE → VERIFYING → ESCALATING → RESOLVED / CANCELLED
        AI_DETECTION → VERIFYING → ESCALATING / CANCELLED
    """

    __tablename__ = "emergency_incidents"
    __table_args__ = (
        Index("ix_emergency_incidents_user_id_status", "user_id", "status"),
        Index("ix_emergency_incidents_status", "status"),
        Index("ix_emergency_incidents_created_at", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(GUID, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        GUID,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # ─── Classification ───────────────────────────────────────────────────
    trigger_type: Mapped[str] = mapped_column(
        trigger_type_enum, nullable=False, default="MANUAL_SOS"
    )
    status: Mapped[str] = mapped_column(incident_status_enum, nullable=False, default="ACTIVE")
    risk_level: Mapped[str] = mapped_column(risk_level_enum, nullable=False, default="CRITICAL")
    # Populated from AI engine result; null for manual SOS
    risk_score: Mapped[float | None] = mapped_column(Float, nullable=True)

    # ─── Location ─────────────────────────────────────────────────────────
    # Latest known location (continuously updated during active incident)
    latitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    longitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    location_accuracy: Mapped[float | None] = mapped_column(Float, nullable=True)
    location_updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # ─── AI Context ───────────────────────────────────────────────────────
    # Reasons list from AI engine (e.g. ["Distress signal detected", ...])
    ai_reasons: Mapped[list[Any] | None] = mapped_column(JSON, nullable=True)

    # ─── Policy Snapshot ─────────────────────────────────────────────────
    # Snapshot of the active policy at incident creation time for auditability
    policy_snapshot: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)

    # ─── Escalation state ─────────────────────────────────────────────────
    # Celery task ID for the active verification timeout task
    # Stored so it can be revoked if the user responds
    escalation_task_id: Mapped[str | None] = mapped_column(String(255), nullable=True)

    # ─── Timestamps ───────────────────────────────────────────────────────
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # ─── Relationships ────────────────────────────────────────────────────
    user: Mapped[User] = relationship(
        "User", back_populates="emergency_incidents", lazy="noload"
    )
    events: Mapped[list[IncidentEvent]] = relationship(
        "IncidentEvent",
        back_populates="incident",
        lazy="noload",
        order_by="IncidentEvent.created_at",
        cascade="all, delete-orphan",
    )
    location_updates: Mapped[list[IncidentLocationUpdate]] = relationship(
        "IncidentLocationUpdate",
        back_populates="incident",
        lazy="noload",
        order_by="IncidentLocationUpdate.recorded_at",
        cascade="all, delete-orphan",
    )

    @property
    def is_active(self) -> bool:
        return self.status in (
            IncidentStatus.ACTIVE,
            IncidentStatus.VERIFYING,
            IncidentStatus.ESCALATING,
        )

    def __repr__(self) -> str:
        return (
            f"<EmergencyIncident id={self.id} user_id={self.user_id} "
            f"status={self.status} trigger={self.trigger_type}>"
        )


class IncidentEvent(Base):
    """
    Immutable timeline event for an emergency incident.

    Every state change, notification, user response, and system action
    is recorded here. This is the audit trail and the data that powers
    the incident timeline display.
    """

    __tablename__ = "incident_events"
    __table_args__ = (
        Index("ix_incident_events_incident_id", "incident_id"),
        Index("ix_incident_events_created_at", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(GUID, primary_key=True, default=uuid.uuid4)
    incident_id: Mapped[uuid.UUID] = mapped_column(
        GUID,
        ForeignKey("emergency_incidents.id", ondelete="CASCADE"),
        nullable=False,
    )
    event_type: Mapped[str] = mapped_column(event_type_enum, nullable=False)
    description: Mapped[str] = mapped_column(String(1000), nullable=False)

    # Optional structured context (contact name, risk score, etc.)
    # Note: Column in DB is named 'metadata', mapped to event_metadata attribute in Python
    event_metadata: Mapped[dict[str, Any] | None] = mapped_column("metadata", JSON, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    incident: Mapped[EmergencyIncident] = relationship(
        "EmergencyIncident", back_populates="events", lazy="noload"
    )

    def __init__(
        self,
        incident_id: uuid.UUID | None = None,
        event_type: str | None = None,
        description: str | None = None,
        metadata: dict[str, Any] | None = None,
        event_metadata: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> None:
        actual_metadata = metadata if metadata is not None else event_metadata
        super().__init__(
            incident_id=incident_id,
            event_type=event_type,
            description=description,
            event_metadata=actual_metadata,
            **kwargs,
        )

    def __repr__(self) -> str:
        return f"<IncidentEvent {self.event_type} incident_id={self.incident_id}>"


class IncidentLocationUpdate(Base):
    """
    A single location ping during an active emergency incident.

    Every update from the mobile app is stored here for:
    - Replay / incident reconstruction
    - Path visualization
    - Audit trail

    The latest values are also mirrored on EmergencyIncident for fast reads.
    """

    __tablename__ = "incident_location_updates"
    __table_args__ = (
        Index("ix_location_updates_incident_id", "incident_id"),
        Index("ix_location_updates_recorded_at", "recorded_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(GUID, primary_key=True, default=uuid.uuid4)
    incident_id: Mapped[uuid.UUID] = mapped_column(
        GUID,
        ForeignKey("emergency_incidents.id", ondelete="CASCADE"),
        nullable=False,
    )
    latitude: Mapped[float] = mapped_column(Float, nullable=False)
    longitude: Mapped[float] = mapped_column(Float, nullable=False)
    accuracy: Mapped[float | None] = mapped_column(Float, nullable=True)

    recorded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    incident: Mapped[EmergencyIncident] = relationship(
        "EmergencyIncident", back_populates="location_updates", lazy="noload"
    )

    def __repr__(self) -> str:
        return (
            f"<IncidentLocationUpdate incident_id={self.incident_id} "
            f"lat={self.latitude} lon={self.longitude}>"
        )
