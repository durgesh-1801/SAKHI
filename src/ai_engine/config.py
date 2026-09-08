"""Centralized Configuration for SAKHI AI / Risk Engine.

All scoring weights, classification thresholds, and engine parameters are centralized here.
Values can be overridden via environment variables with prefix SAKHI_AI_.

IMPORTANT:
These initial weights are rule-based heuristics and are NOT scientifically validated.
This configuration is designed so individual detector weights and thresholds can be tuned
or substituted as empirical safety datasets and ML models are introduced.
"""

from typing import Dict
from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class SignalWeights(BaseModel):
    """Configurable weights for each safety signal.

    Weights represent positive risk contributions towards danger severity.
    """

    manual_sos: float = Field(
        default=50.0,
        description="Manual SOS trigger indicates immediate explicit user distress.",
    )
    distress_audio: float = Field(
        default=35.0,
        description="Distress sound or scream detected.",
    )
    distress_keywords: float = Field(
        default=25.0,
        description="Spoken distress keywords detected in audio.",
    )
    sudden_fall: float = Field(
        default=25.0,
        description="Sudden drop/fall impact detected by accelerometer.",
    )
    abnormal_motion: float = Field(
        default=15.0,
        description="Erratic or struggling motion pattern detected.",
    )
    sudden_running: float = Field(
        default=15.0,
        description="Sudden transition to high-velocity running/fleeing.",
    )
    route_deviation: float = Field(
        default=15.0,
        description="Significant deviation from expected journey route.",
    )
    inactivity: float = Field(
        default=15.0,
        description="Prolonged lack of movement or phone interaction during journey.",
    )
    sensor_anomalies: float = Field(
        default=10.0,
        description="Environmental or sensor readings outside normal bounds.",
    )
    no_response: float = Field(
        default=20.0,
        description="User failed to respond to safety verification prompt.",
    )

    def to_dict(self) -> Dict[str, float]:
        """Convert weights model to a dictionary."""
        return self.model_dump()


class RiskThresholds(BaseModel):
    """Configurable boundary thresholds for risk classification.

    Scores range from 0 to 100:
    0  - safe_max       -> SAFE
    safe_max+1 - suspicious_max -> SUSPICIOUS
    suspicious_max+1 - high_max -> HIGH
    high_max+1 - 100    -> CRITICAL
    """

    safe_max: float = Field(
        default=30.0,
        description="Upper score bound for SAFE status (inclusive).",
    )
    suspicious_max: float = Field(
        default=60.0,
        description="Upper score bound for SUSPICIOUS status (inclusive).",
    )
    high_max: float = Field(
        default=80.0,
        description="Upper score bound for HIGH status (inclusive).",
    )
    critical_min: float = Field(
        default=81.0,
        description="Lower score bound for CRITICAL status (inclusive).",
    )


class RiskEngineSettings(BaseSettings):
    """Global configuration settings for SAKHI AI / Risk Engine."""

    model_config = SettingsConfigDict(
        env_prefix="SAKHI_AI_",
        env_nested_delimiter="__",
        case_sensitive=False,
    )

    app_name: str = "SAKHI AI Risk Engine"
    app_version: str = "0.1.0"
    debug: bool = False

    min_score: float = 0.0
    max_score: float = 100.0

    # Default weights and classification thresholds
    weights: SignalWeights = Field(default_factory=SignalWeights)
    thresholds: RiskThresholds = Field(default_factory=RiskThresholds)


# Default settings instance
settings = RiskEngineSettings()
