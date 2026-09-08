"""Pydantic Schemas for SAKHI AI / Risk Engine.

Defines the stable API contracts for signal ingestion, validation, and risk analysis responses.
Includes strict type checking and range validations to prevent invalid data from corrupting risk scores.
"""

from enum import Enum
from typing import List, Optional, Dict, Any
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
    manual_sos: Optional[bool] = Field(
        default=False,
        description="Explicit user-triggered SOS button.",
    )

    # 2. Audio signals
    distress_audio: Optional[bool] = Field(
        default=False,
        description="Distress sound or scream detected.",
    )
    audio_confidence: Optional[float] = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description="Confidence score for distress audio (0.0 to 1.0).",
    )

    # 3. Distress keywords
    distress_keywords: Optional[bool] = Field(
        default=False,
        description="Spoken distress keywords detected in speech stream.",
    )
    keyword_confidence: Optional[float] = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description="Confidence score for distress keywords (0.0 to 1.0).",
    )

    # 4. Motion and Fall signals
    sudden_fall: Optional[bool] = Field(
        default=False,
        description="Accelerometer impact indicating sudden fall or drop.",
    )
    fall_confidence: Optional[float] = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description="Confidence score for sudden fall (0.0 to 1.0).",
    )
    abnormal_motion: Optional[bool] = Field(
        default=False,
        description="Erratic motion indicating struggling or physical altercation.",
    )
    motion_anomaly_score: Optional[float] = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description="Processed anomaly score for motion (0.0 to 1.0).",
    )
    sudden_running: Optional[bool] = Field(
        default=False,
        description="Sudden transition to high-velocity running.",
    )

    # 5. Route and Journey signals
    route_deviation: Optional[bool] = Field(
        default=False,
        description="Significant deviation from planned route.",
    )
    route_deviation_score: Optional[float] = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description="Processed score for route deviation (0.0 to 1.0).",
    )
    inactivity: Optional[bool] = Field(
        default=False,
        description="Prolonged lack of movement or responsiveness.",
    )

    # 6. Environmental and Sensor anomalies
    sensor_anomalies: Optional[bool] = Field(
        default=False,
        description="Sensor or environmental reading anomalies detected.",
    )

    # 7. User verification response
    no_response: Optional[bool] = Field(
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
    def validate_confidence_range(cls, v: Optional[float]) -> Optional[float]:
        """Ensure confidence values are strictly within [0.0, 1.0] and not NaN."""
        if v is not None:
            if v < 0.0 or v > 1.0:
                raise ValueError("Confidence or anomaly score must be between 0.0 and 1.0")
        return v


class AIAnalyzeRequest(BaseModel):
    """Request payload for the AI Risk Engine analysis endpoint."""

    model_config = ConfigDict(
        extra="forbid",
    )

    user_id: str = Field(
        ...,
        min_length=1,
        description="Identifier of the user for context logging (without storing sensitive PII).",
        examples=["user_12345"],
    )
    signals: SignalsPayload = Field(
        ...,
        description="Collection of safety signals and derived features.",
    )
    timestamp: Optional[str] = Field(
        default=None,
        description="ISO 8601 timestamp of signal capture.",
    )


class SignalDetail(BaseModel):
    """Detailed breakdown of an individual signal evaluation."""

    signal_name: str
    detected: bool
    weight_contributed: float
    confidence: Optional[float] = None
    reason: Optional[str] = None
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
    reasons: List[str] = Field(
        ...,
        description="Human-readable explainable list of contributing risk factors.",
        examples=[
            "Distress audio detected",
            "Sudden fall detected",
            "Abnormal motion detected",
            "No user response detected",
        ],
    )
    signals_detected: List[str] = Field(
        ...,
        description="List of signal identifiers that contributed to the risk score.",
        examples=[
            "distress_audio",
            "sudden_fall",
            "abnormal_motion",
            "no_response",
        ],
    )
    details: Optional[Dict[str, SignalDetail]] = Field(
        default=None,
        description="Optional diagnostic breakdown of individual detector outputs.",
    )
