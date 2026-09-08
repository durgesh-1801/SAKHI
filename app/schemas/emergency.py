"""
ARIA / SAKHI — Emergency Schemas (Pydantic v2)
================================================
BE3 OWNS THIS FILE.

All request and response schemas for the emergency domain.
"""

import uuid
from datetime import datetime
from typing import Any

from pydantic import AliasChoices, BaseModel, ConfigDict, Field, field_validator

# ─── Enums (string literals — matches DB enum values) ─────────────────────────


class RiskLevelEnum(str):
    SAFE = "SAFE"
    SUSPICIOUS = "SUSPICIOUS"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class IncidentStatusEnum(str):
    ACTIVE = "ACTIVE"
    VERIFYING = "VERIFYING"
    ESCALATING = "ESCALATING"
    RESOLVED = "RESOLVED"
    CANCELLED = "CANCELLED"


class TriggerTypeEnum(str):
    MANUAL_SOS = "MANUAL_SOS"
    AI_DETECTION = "AI_DETECTION"
    FALL_DETECTION = "FALL_DETECTION"
    DISTRESS_DETECTION = "DISTRESS_DETECTION"
    SAFE_JOURNEY = "SAFE_JOURNEY"
    OTHER = "OTHER"


# ─── Request Schemas ──────────────────────────────────────────────────────────


class SOSRequest(BaseModel):
    """
    Manual SOS trigger request body.
    All fields are optional — the user may trigger SOS without initial location.
    """

    latitude: float | None = Field(None, ge=-90.0, le=90.0, description="Current latitude")
    longitude: float | None = Field(None, ge=-180.0, le=180.0, description="Current longitude")
    accuracy: float | None = Field(None, ge=0.0, description="GPS accuracy in metres")


class AITriggerRequest(BaseModel):
    """
    AI risk result delivered by Backend Engineer 1.
    Triggers an emergency flow if the user has consented to AI monitoring.
    """

    user_id: uuid.UUID = Field(..., description="The user at risk (from AI engine context)")
    risk_score: float = Field(..., ge=0.0, le=100.0, description="Risk score 0–100")
    risk_level: str = Field(..., description="SAFE | SUSPICIOUS | HIGH | CRITICAL")
    reasons: list[str] = Field(default_factory=list, description="Explainable risk reasons")
    trigger_type: str = Field(
        default="AI_DETECTION",
        description="AI_DETECTION | FALL_DETECTION | DISTRESS_DETECTION",
    )
    latitude: float | None = Field(None, ge=-90.0, le=90.0)
    longitude: float | None = Field(None, ge=-180.0, le=180.0)

    @field_validator("risk_level")
    @classmethod
    def validate_risk_level(cls, v: str) -> str:
        valid = {"SAFE", "SUSPICIOUS", "HIGH", "CRITICAL"}
        if v not in valid:
            raise ValueError(f"risk_level must be one of {valid}")
        return v

    @field_validator("trigger_type")
    @classmethod
    def validate_trigger_type(cls, v: str) -> str:
        valid = {"AI_DETECTION", "FALL_DETECTION", "DISTRESS_DETECTION", "OTHER"}
        if v not in valid:
            raise ValueError(f"trigger_type must be one of {valid}")
        return v


class VerifyRequest(BaseModel):
    """User's response to the 'Are you safe?' verification request."""

    response: str = Field(
        ...,
        description="USER_CONFIRMED_SAFE | USER_REQUESTED_HELP",
    )

    @field_validator("response")
    @classmethod
    def validate_response(cls, v: str) -> str:
        valid = {"USER_CONFIRMED_SAFE", "USER_REQUESTED_HELP"}
        if v not in valid:
            raise ValueError(f"response must be one of {valid}")
        return v


class LocationUpdateRequest(BaseModel):
    """
    Location update from mobile app during active emergency.
    Sent via WebSocket (client → server).
    """

    latitude: float = Field(..., ge=-90.0, le=90.0)
    longitude: float = Field(..., ge=-180.0, le=180.0)
    accuracy: float | None = Field(None, ge=0.0)


# ─── Response Schemas ─────────────────────────────────────────────────────────


class IncidentEventRead(BaseModel):
    id: uuid.UUID
    incident_id: uuid.UUID
    event_type: str
    description: str
    metadata: dict[str, Any] | None = Field(
        default=None,
        validation_alias=AliasChoices("metadata", "event_metadata"),
    )
    created_at: datetime

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)


class IncidentLocationRead(BaseModel):
    id: uuid.UUID
    incident_id: uuid.UUID
    latitude: float
    longitude: float
    accuracy: float | None = None
    recorded_at: datetime

    model_config = {"from_attributes": True}


class EmergencyIncidentRead(BaseModel):
    """Full incident detail returned to the authenticated user."""

    id: uuid.UUID
    user_id: uuid.UUID
    trigger_type: str
    status: str
    risk_level: str
    risk_score: float | None = None
    latitude: float | None = None
    longitude: float | None = None
    location_accuracy: float | None = None
    location_updated_at: datetime | None = None
    ai_reasons: list[str] | None = None
    created_at: datetime
    updated_at: datetime
    resolved_at: datetime | None = None

    model_config = {"from_attributes": True}


class EmergencyIncidentWithTimeline(EmergencyIncidentRead):
    """Incident detail including the full event timeline."""

    events: list[IncidentEventRead] = []


class SOSResponse(BaseModel):
    """Response to a successful SOS trigger."""

    incident_id: uuid.UUID
    status: str
    risk_level: str
    message: str = "Emergency incident created. Escalation has started."


class VerifyResponse(BaseModel):
    """Response to a verification answer."""

    incident_id: uuid.UUID
    status: str
    message: str


class LocationResponse(BaseModel):
    """Latest location for an incident (guardian-only endpoint)."""

    incident_id: uuid.UUID
    latitude: float | None
    longitude: float | None
    location_accuracy: float | None
    location_updated_at: datetime | None
    status: str


# ─── WebSocket Event Schemas ──────────────────────────────────────────────────


class WSLocationUpdate(BaseModel):
    """Server → guardian: live location broadcast."""

    event: str = "location_update"
    incident_id: str
    latitude: float
    longitude: float
    accuracy: float | None = None
    timestamp: str


class WSIncidentUpdate(BaseModel):
    """Server → all: incident status change."""

    event: str = "incident_update"
    incident_id: str
    status: str
    timestamp: str


class WSVerificationRequest(BaseModel):
    """Server → user: 'Are you safe?' prompt."""

    event: str = "verification_request"
    incident_id: str
    message: str = "Are you safe? Respond within the configured timeout."
    expires_at: str


class WSContactNotified(BaseModel):
    """Server → user: confirmation a contact was notified."""

    event: str = "contact_notified"
    incident_id: str
    contact_name: str
    timestamp: str


class WSIncidentResolved(BaseModel):
    """Server → all: incident closed."""

    event: str = "incident_resolved"
    incident_id: str
    resolved_by: str  # "USER" | "TIMEOUT" | "SYSTEM"
    timestamp: str


class WSError(BaseModel):
    """Server → client: error event."""

    event: str = "error"
    code: str
    message: str


# ─── Guardian Update Schema (notification payload) ────────────────────────────


class GuardianAlertPayload(BaseModel):
    """
    Structured payload sent to trusted contacts as emergency alert.
    Used by the notification dispatcher.
    """

    incident_id: str
    user_name: str
    risk_level: str
    ai_reasons: list[str] | None = None
    timestamp: str
    has_live_location: bool = False
    location_url: str | None = None  # deep-link to guardian dashboard
