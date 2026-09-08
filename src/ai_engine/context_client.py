"""Backend 2 Context Client & Consent Enforcer for SAKHI AI / Risk Engine.

Retrieves user consent and active journey context from Backend 2 (Core Backend & Data Layer).
Enforces consent boundaries before processing safety data:
- RULE 1: If ai_detection_permitted is False, abort safety inference.
- RULE 2: If audio_analysis_permitted is False, strip all audio signals and reject audio uploads.
- RULE 3: If location_monitoring_permitted is False, strip route deviation and location signals.
Backend 2 is the single source of truth for consent; Backend 1 stores zero consent data.
"""

import logging
from typing import Any

from fastapi import HTTPException, status
from pydantic import BaseModel

from .schemas import SignalsPayload

logger = logging.getLogger("sakhi.ai_engine.context")


class UserContext(BaseModel):
    """User context model received from Backend 2."""

    user_id: str
    ai_detection_permitted: bool
    audio_analysis_permitted: bool
    location_monitoring_permitted: bool
    active_journey: dict[str, Any] | None = None
    consent: dict[str, Any] | None = None


class Backend2ContextClient:
    """Client for querying user context and consent from Backend 2.

    Supports both in-process resolution (when unified with app database session)
    and service-to-service HTTP requests across microservices.
    """

    def __init__(self, backend_url: str | None = None, service_key: str | None = None):
        self.backend_url = backend_url
        self.service_key = service_key

    def get_context(self, user_id: str, db_session: Any | None = None) -> UserContext:
        """Fetch user context and consent from Backend 2.

        Raises:
            HTTPException(404): If user does not exist.
            HTTPException(503): If Backend 2 is unreachable.
        """
        # 1. In-process direct resolution if database session is provided
        if db_session is not None:
            try:
                from app.core.exceptions import EntityNotFoundException
                from app.services.context_service import context_service

                b2_context = context_service.get_ai_risk_context(db_session, user_id)
                return UserContext(
                    user_id=b2_context.user_id,
                    ai_detection_permitted=b2_context.ai_detection_permitted,
                    audio_analysis_permitted=b2_context.audio_analysis_permitted,
                    location_monitoring_permitted=b2_context.location_monitoring_permitted,
                    active_journey=b2_context.active_journey.model_dump() if b2_context.active_journey else None,
                    consent=b2_context.consent.model_dump() if b2_context.consent else None,
                )
            except EntityNotFoundException:
                logger.warning("User %s not found in Backend 2", user_id)
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"User {user_id} not found in SAKHI core database.",
                )
            except Exception:
                logger.exception("Failed to query Backend 2 context in-process")
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail="Core Backend context service is currently unavailable.",
                )

        # 2. HTTP service-to-service resolution if URL is configured
        if self.backend_url:
            import httpx

            url = f"{self.backend_url.rstrip('/')}/api/v1/context/ai-risk/{user_id}"
            headers = {}
            if self.service_key:
                headers["X-Internal-Service-Key"] = self.service_key

            try:
                with httpx.Client(timeout=5.0) as client:
                    response = client.get(url, headers=headers)
                    if response.status_code == 404:
                        raise HTTPException(
                            status_code=status.HTTP_404_NOT_FOUND,
                            detail=f"User {user_id} not found in SAKHI core database.",
                        )
                    if response.status_code != 200:
                        raise HTTPException(
                            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                            detail="Core Backend returned an error resolving AI context.",
                        )
                    data = response.json()
                    return UserContext(**data)
            except httpx.RequestError:
                logger.exception("Network error contacting Backend 2")
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail="Core Backend is unreachable for consent and context resolution.",
                )

        # 3. Fallback: If no db session and no backend url, check if app is importable
        try:
            from app.core.exceptions import EntityNotFoundException
            from app.database import SessionLocal
            from app.services.context_service import context_service

            with SessionLocal() as db:
                b2_context = context_service.get_ai_risk_context(db, user_id)
                return UserContext(
                    user_id=b2_context.user_id,
                    ai_detection_permitted=b2_context.ai_detection_permitted,
                    audio_analysis_permitted=b2_context.audio_analysis_permitted,
                    location_monitoring_permitted=b2_context.location_monitoring_permitted,
                    active_journey=b2_context.active_journey.model_dump() if b2_context.active_journey else None,
                    consent=b2_context.consent.model_dump() if b2_context.consent else None,
                )
        except EntityNotFoundException:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"User {user_id} not found in SAKHI core database.",
            )
        except Exception:
            logger.exception("Failed to query Backend 2 fallback")
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Core Backend context service is unavailable.",
            )


class ConsentEnforcer:
    """Enforces consent rules on incoming safety signal payloads."""

    @staticmethod
    def enforce(context: UserContext, signals: SignalsPayload) -> tuple[SignalsPayload, dict[str, Any]]:
        """Applies consent rules to incoming signals.

        Returns:
            Tuple of (sanitized_signals, audit_metadata).

        Raises:
            HTTPException(403): If AI detection is disabled by user consent.
        """
        audit_metadata: dict[str, Any] = {
            "ai_detection_permitted": context.ai_detection_permitted,
            "audio_analysis_permitted": context.audio_analysis_permitted,
            "location_monitoring_permitted": context.location_monitoring_permitted,
            "stripped_signals": [],
        }

        # RULE 1: If ai_detection_permitted is False, abort AI safety inference immediately.
        if not context.ai_detection_permitted:
            logger.warning(
                "Consent enforcement: AI detection is disabled for user=%s",
                context.user_id,
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={
                    "error": "AI_CONSENT_REVOKED",
                    "message": "AI safety detection is disabled by user consent policy.",
                    "user_id": context.user_id,
                },
            )

        sanitized_dict = signals.model_dump()

        # RULE 2: If audio_analysis_permitted is False, strip all audio signals.
        if not context.audio_analysis_permitted:
            audio_fields = ["distress_audio", "audio_confidence", "distress_keywords", "keyword_confidence"]
            for field in audio_fields:
                if sanitized_dict.get(field):
                    audit_metadata["stripped_signals"].append(field)
                if "confidence" in field:
                    sanitized_dict[field] = None
                else:
                    sanitized_dict[field] = False
            logger.info("Consent enforcement: Stripped audio signals for user=%s", context.user_id)

        # RULE 3: If location_monitoring_permitted is False, strip route deviation signals.
        if not context.location_monitoring_permitted:
            location_fields = ["route_deviation", "route_deviation_score"]
            for field in location_fields:
                if sanitized_dict.get(field):
                    audit_metadata["stripped_signals"].append(field)
                if "score" in field:
                    sanitized_dict[field] = None
                else:
                    sanitized_dict[field] = False
            logger.info("Consent enforcement: Stripped location signals for user=%s", context.user_id)

        sanitized_signals = SignalsPayload(**sanitized_dict)
        return sanitized_signals, audit_metadata


# Global context client instance
context_client = Backend2ContextClient()
