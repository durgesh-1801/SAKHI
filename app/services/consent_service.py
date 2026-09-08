"""
ARIA / SAKHI — Consent Service
================================
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
