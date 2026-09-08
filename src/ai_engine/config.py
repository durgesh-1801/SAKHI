"""Centralized Configuration for SAKHI AI / Risk Engine.

All scoring weights, classification thresholds, and engine parameters are centralized here.
Values can be overridden via environment variables with prefix SAKHI_AI_.

IMPORTANT:
These initial weights are rule-based heuristics and are NOT scientifically validated.
This configuration is designed so individual detector weights and thresholds can be tuned
or substituted as empirical safety datasets and ML models are introduced.
"""


import os

from pydantic import BaseModel, Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class SignalWeights(BaseModel):
    """Configurable weights for each safety signal.

    Weights represent non-negative positive risk contributions towards danger severity.
    Negative weights are rejected to prevent dangerous signals from reducing risk.
    """

    manual_sos: float = Field(
        default=50.0,
        ge=0.0,
        description="Manual SOS trigger indicates immediate explicit user distress.",
    )
    distress_audio: float = Field(
        default=35.0,
        ge=0.0,
        description="Distress sound or scream detected.",
    )
    distress_keywords: float = Field(
        default=25.0,
        ge=0.0,
        description="Spoken distress keywords detected in audio.",
    )
    sudden_fall: float = Field(
        default=25.0,
        ge=0.0,
        description="Sudden drop/fall impact detected by accelerometer.",
    )
    abnormal_motion: float = Field(
        default=15.0,
        ge=0.0,
        description="Erratic or struggling motion pattern detected.",
    )
    sudden_running: float = Field(
        default=15.0,
        ge=0.0,
        description="Sudden transition to high-velocity running/fleeing.",
    )
    route_deviation: float = Field(
        default=15.0,
        ge=0.0,
        description="Significant deviation from expected journey route.",
    )
    inactivity: float = Field(
        default=15.0,
        ge=0.0,
        description="Prolonged lack of movement or phone interaction during journey.",
    )
    sensor_anomalies: float = Field(
        default=10.0,
        ge=0.0,
        description="Environmental or sensor readings outside normal bounds.",
    )
    no_response: float = Field(
        default=20.0,
        ge=0.0,
        description="User failed to respond to safety verification prompt.",
    )

    def to_dict(self) -> dict[str, float]:
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
        ge=0.0,
        le=100.0,
        description="Upper score bound for SAFE status (inclusive).",
    )
    suspicious_max: float = Field(
        default=60.0,
        ge=0.0,
        le=100.0,
        description="Upper score bound for SUSPICIOUS status (inclusive).",
    )
    high_max: float = Field(
        default=80.0,
        ge=0.0,
        le=100.0,
        description="Upper score bound for HIGH status (inclusive).",
    )
    critical_min: float = Field(
        default=81.0,
        ge=0.0,
        le=100.0,
        description="Lower score bound for CRITICAL status (inclusive).",
    )

    @model_validator(mode="after")
    def validate_threshold_order(self) -> "RiskThresholds":
        """Ensure threshold levels are strictly ordered: safe < suspicious < high <= critical."""
        if not (0.0 <= self.safe_max < self.suspicious_max < self.high_max <= self.critical_min <= 100.0):
            raise ValueError(
                f"Invalid threshold ordering: safe_max ({self.safe_max}) < "
                f"suspicious_max ({self.suspicious_max}) < "
                f"high_max ({self.high_max}) <= "
                f"critical_min ({self.critical_min}) must hold strictly within [0, 100]."
            )
        return self


class WhisperSettings(BaseModel):
    """Configuration for local offline Whisper Speech-to-Text inference.

    Supports both SAKHI_AI_WHISPER__* environment variables and standard
    WHISPER_* environment variables.
    """

    model_size: str = Field(
        default_factory=lambda: os.getenv("WHISPER_MODEL_SIZE", "tiny"),
        description="Pretrained Whisper model size (tiny, base, small, medium, large-v3).",
    )
    model_path: str | None = Field(
        default_factory=lambda: os.getenv("WHISPER_MODEL_PATH", None),
        description="Local directory path to model weights or HuggingFace repo ID.",
    )
    device: str = Field(
        default_factory=lambda: os.getenv("WHISPER_DEVICE", "cpu"),
        description="Device for Whisper inference ('cpu' or 'cuda').",
    )
    compute_type: str = Field(
        default_factory=lambda: os.getenv("WHISPER_COMPUTE_TYPE", "int8"),
        description="Quantization compute type ('int8', 'float16', 'float32', 'default').",
    )
    language: str | None = Field(
        default_factory=lambda: os.getenv("WHISPER_LANGUAGE", None),
        description="Target language code (e.g. 'en', 'hi') or None/'auto' for automatic language detection.",
    )
    enabled: bool = Field(
        default=True,
        description="Whether STT processing is enabled in the audio pipeline.",
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

    # Default weights, classification thresholds, and STT config
    weights: SignalWeights = Field(default_factory=SignalWeights)
    thresholds: RiskThresholds = Field(default_factory=RiskThresholds)
    whisper: WhisperSettings = Field(default_factory=WhisperSettings)


# Default settings instance
settings = RiskEngineSettings()

