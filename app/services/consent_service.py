"""
ARIA / SAKHI — Consent Service
⚠️  BE2 ZONE — BE3 calls these functions as gates before emergency actions.
    BE2 replaces stub bodies with real DB queries.

BE3 CONTRACT (do not change function signatures):
    can_share_location(user_id, db) -> bool
    can_auto_escalate(user_id, db) -> bool
    can_act_on_ai_result(user_id, db) -> bool

IMPORTANT:
    If consent is not configured, BE3 defaults to DENY for AI-driven actions
    and ALLOW for manual SOS (the user explicitly triggered it).
    This matches the consent-first philosophy in the README.
"""

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.consent import UserConsent


async def _get_consent(user_id: uuid.UUID, db: AsyncSession) -> UserConsent | None:
    result = await db.execute(select(UserConsent).where(UserConsent.user_id == user_id))
    return result.scalar_one_or_none()


async def can_share_location(user_id: uuid.UUID, db: AsyncSession) -> bool:
    """
    Returns True if the user has consented to location sharing.
    Default: False (deny) — requires explicit opt-in.

    BE2: Replace with real consent check if additional logic is needed.
    """
    consent = await _get_consent(user_id, db)
    if consent is None:
        return False  # Deny by default — consent-first
    return consent.allow_location_sharing


async def can_auto_escalate(user_id: uuid.UUID, db: AsyncSession) -> bool:
    """
    Returns True if the user has consented to automatic escalation.
    Default: False (deny) — requires explicit opt-in.

    For MANUAL_SOS, BE3 bypasses this check because the user explicitly triggered it.
    """
    consent = await _get_consent(user_id, db)
    if consent is None:
        return False
    return consent.allow_auto_escalation


async def can_act_on_ai_result(user_id: uuid.UUID, db: AsyncSession) -> bool:
    """
    Returns True if the user has consented to AI-driven monitoring.
    An AI risk result from BE1 should only trigger emergency flow if this is True.
    """
    consent = await _get_consent(user_id, db)
    if consent is None:
        return False
    return consent.allow_ai_monitoring
from sqlalchemy.orm import Session
from app.models.consent import UserConsent
from app.schemas.consent import ConsentUpdate
from app.core.exceptions import EntityNotFoundException


class ConsentService:
    @staticmethod
    def get_or_create_consent(db: Session, user_id: str) -> UserConsent:
        consent = db.query(UserConsent).filter(UserConsent.user_id == user_id).first()
        if not consent:
            consent = UserConsent(
                user_id=user_id,
                location_monitoring=False,
                ai_detection=False,
                audio_analysis=False,
                automatic_escalation=False,
                evidence_collection=False
            )
            db.add(consent)
            db.commit()
            db.refresh(consent)
        return consent

    @staticmethod
    def update_consent(db: Session, user_id: str, consent_in: ConsentUpdate) -> UserConsent:
        consent = ConsentService.get_or_create_consent(db, user_id)

        if consent_in.location_monitoring is not None:
            consent.location_monitoring = consent_in.location_monitoring
        if consent_in.ai_detection is not None:
            consent.ai_detection = consent_in.ai_detection
        if consent_in.audio_analysis is not None:
            consent.audio_analysis = consent_in.audio_analysis
        if consent_in.automatic_escalation is not None:
            consent.automatic_escalation = consent_in.automatic_escalation
        if consent_in.evidence_collection is not None:
            consent.evidence_collection = consent_in.evidence_collection

        db.commit()
        db.refresh(consent)
        return consent


consent_service = ConsentService()
