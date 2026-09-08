"""Pydantic Schemas for SAKHI AI / Risk Engine.

Defines the stable API contracts for signal ingestion, validation, and risk analysis responses.
Includes strict type checking and range validations to prevent invalid data from corrupting risk scores.
"""

import math
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field, field_validator


class RiskLevel(str, Enum):
    """Standard Risk Levels for SAKHI safety assessment."""

    SAFE = "SAFE"
    SUSPICIOUS = "SUSPICIOUS"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class SignalsPayload(BaseModel):
    """Safety signals provided to the AI / Risk Engine.

    Accepts both high-level boolean detection flags and processed feature scores.
    Rejects unknown fields to prevent unrecognized signals from corrupting scoring.
    """

    model_config = ConfigDict(
        extra="forbid",
        validate_assignment=True,
    )

    # 1. Manual SOS
    manual_sos: bool | None = Field(
        default=False,
        description="Explicit user-triggered SOS button.",
    )

    # 2. Audio signals
    distress_audio: bool | None = Field(
        default=False,
        description="Distress sound or scream detected.",
    )
    audio_confidence: float | None = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description="Confidence score for distress audio (0.0 to 1.0).",
    )

    # 3. Distress keywords
    distress_keywords: bool | None = Field(
        default=False,
        description="Spoken distress keywords detected in speech stream.",
    )
    keyword_confidence: float | None = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description="Confidence score for distress keywords (0.0 to 1.0).",
    )

    # 4. Motion and Fall signals
    sudden_fall: bool | None = Field(
        default=False,
        description="Accelerometer impact indicating sudden fall or drop.",
    )
    fall_confidence: float | None = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description="Confidence score for sudden fall (0.0 to 1.0).",
    )
    abnormal_motion: bool | None = Field(
        default=False,
        description="Erratic motion indicating struggling or physical altercation.",
    )
    motion_anomaly_score: float | None = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description="Processed anomaly score for motion (0.0 to 1.0).",
    )
    sudden_running: bool | None = Field(
        default=False,
        description="Sudden transition to high-velocity running.",
    )

    # 5. Route and Journey signals
    route_deviation: bool | None = Field(
        default=False,
        description="Significant deviation from planned route.",
    )
    route_deviation_score: float | None = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description="Processed score for route deviation (0.0 to 1.0).",
    )
    inactivity: bool | None = Field(
        default=False,
        description="Prolonged lack of movement or responsiveness.",
    )

    # 6. Environmental and Sensor anomalies
    sensor_anomalies: bool | None = Field(
        default=False,
        description="Sensor or environmental reading anomalies detected.",
    )

    # 7. User verification response
    no_response: bool | None = Field(
        default=False,
        description="User failed to respond to verification prompt within timeout.",
    )

    @field_validator(
        "audio_confidence",
        "keyword_confidence",
        "fall_confidence",
        "motion_anomaly_score",
        "route_deviation_score",
    )
    @classmethod
    def validate_confidence_range(cls, v: float | None) -> float | None:
        """Ensure confidence values are finite and strictly within [0.0, 1.0]."""
        if v is not None and (not math.isfinite(v) or v < 0.0 or v > 1.0):
            raise ValueError("Confidence or anomaly score must be a finite number between 0.0 and 1.0")
        return v


class AIAnalyzeRequest(BaseModel):
    """Request payload for the AI Risk Engine analysis endpoint."""

    model_config = ConfigDict(
        extra="forbid",
    )

    user_id: str = Field(
        ...,
        min_length=1,
        max_length=256,
        description="Identifier of the user for context logging (without storing sensitive PII).",
        examples=["user_12345"],
    )
    signals: SignalsPayload = Field(
        ...,
        description="Collection of safety signals and derived features.",
    )
    timestamp: str | None = Field(
        default=None,
        description="ISO 8601 timestamp of signal capture.",
    )

    @field_validator("user_id")
    @classmethod
    def validate_user_id(cls, v: str) -> str:
        """Reject whitespace-only user_id and strip boundary whitespace."""
        stripped = v.strip()
        if not stripped:
            raise ValueError("user_id cannot be blank or whitespace-only")
        if len(stripped) > 256:
            raise ValueError("user_id cannot exceed 256 characters")
        return stripped


class SignalDetail(BaseModel):
    """Detailed breakdown of an individual signal evaluation."""

    signal_name: str
    detected: bool
    weight_contributed: float
    confidence: float | None = None
    reason: str | None = None
    status: str = "SUCCESS"  # SUCCESS, FAILED, SKIPPED


class AIAnalyzeResponse(BaseModel):
    """Stable response structure returned by the SAKHI AI / Risk Engine.

    Guaranteed schema contract for Backend Engineer 2 / 3 integration.
    """

    risk_score: float = Field(
        ...,
        ge=0.0,
        le=100.0,
        description="Aggregated risk score clamped between 0 and 100.",
        examples=[86.0],
    )
    risk_level: RiskLevel = Field(
        ...,
        description="Categorical risk classification: SAFE, SUSPICIOUS, HIGH, CRITICAL.",
        examples=[RiskLevel.CRITICAL],
    )
    reasons: list[str] = Field(
        ...,
        description="Human-readable explainable list of contributing risk factors.",
        examples=[
            "Distress audio detected",
            "Sudden fall detected",
            "Abnormal motion detected",
            "No user response detected",
        ],
    )
    signals_detected: list[str] = Field(
        ...,
        description="List of signal identifiers that contributed to the risk score.",
        examples=[
            "distress_audio",
            "sudden_fall",
            "abnormal_motion",
            "no_response",
        ],
    )
    details: dict[str, SignalDetail] | None = Field(
        default=None,
        description="Optional diagnostic breakdown of individual detector outputs.",
    )
