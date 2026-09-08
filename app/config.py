"""
ARIA / SAKHI — Application Settings
All configuration is loaded from environment variables via pydantic-settings.
Set values in a .env file (copy from .env.example).
"""

from functools import lru_cache

import os
from typing import List, Union
from pydantic import AnyHttpUrl, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ── Application ──────────────────────────────────────────────────────────
    APP_ENV: str = "development"
    APP_NAME: str = "ARIA-SAKHI"
    APP_VERSION: str = "0.1.0"
    DEBUG: bool = False
    SECRET_KEY: str = "change-me"

    # ── Database ─────────────────────────────────────────────────────────────
    DATABASE_URL: str = "postgresql+asyncpg://aria:aria_password@localhost:5432/aria_db"

    # ── Redis / Celery ────────────────────────────────────────────────────────
    REDIS_URL: str = "redis://localhost:6379/0"
    CELERY_BROKER_URL: str = "redis://localhost:6379/1"
    CELERY_RESULT_BACKEND: str = "redis://localhost:6379/2"

    # ── Auth (BE1 fills in internals) ─────────────────────────────────────────
    JWT_SECRET_KEY: str = "change-me-jwt-secret"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30

    # ── Firebase (Push Notifications) ─────────────────────────────────────────
    FIREBASE_CREDENTIALS_PATH: str = "firebase-credentials.json"
    FIREBASE_CREDENTIALS_JSON: str = ""  # Alternative: inline JSON string

    # ── Twilio (SMS — optional) ───────────────────────────────────────────────
    TWILIO_ACCOUNT_SID: str = ""
    TWILIO_AUTH_TOKEN: str = ""
    TWILIO_FROM_NUMBER: str = ""
    SMS_NOTIFICATIONS_ENABLED: bool = False

    # ── Rate Limiting ─────────────────────────────────────────────────────────
    SOS_RATE_LIMIT_PER_MINUTE: int = 5

    # ── Escalation Defaults ───────────────────────────────────────────────────
    # These are fallback values only — the actual values come from the user's
    # emergency policy (BE2). Do not rely on these in production logic.
    DEFAULT_VERIFICATION_TIMEOUT_SECONDS: int = 30


@lru_cache
def get_settings() -> Settings:
    """Return the cached application settings singleton."""
    return Settings()
    PROJECT_NAME: str = "SAKHI Core Backend"
    API_V1_STR: str = "/api/v1"
    SECRET_KEY: str = "sakhi-dev-super-secret-key-change-in-production-min32chars"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24  # 1 day
    ENVIRONMENT: str = "development"
    DATABASE_URL: str = "sqlite:///./sakhi.db"
    ALLOWED_ORIGINS: Union[List[str], str] = ["http://localhost:3000", "http://localhost:5173"]

    @field_validator("ALLOWED_ORIGINS", mode="before")
    @classmethod
    def assemble_cors_origins(cls, v: Union[str, List[str]]) -> List[str]:
        if isinstance(v, str) and not v.startswith("["):
            return [i.strip() for i in v.split(",") if i.strip()]
        elif isinstance(v, list):
            return v
        return ["*"]

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore"
    )


settings = Settings()
