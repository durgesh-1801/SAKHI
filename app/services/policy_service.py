"""
ARIA / SAKHI — Policy Service
===============================
⚠️  BE2 ZONE — BE3 calls these functions but does NOT own them.
    BE2 replaces the stub bodies with real DB queries.

BE3 CONTRACT (do not change function signatures):
    get_emergency_policy(user_id, db) -> EmergencyPolicy | None
    get_policy_or_default(user_id, db) -> EmergencyPolicy
"""

import uuid
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.policy import EmergencyPolicy


async def get_emergency_policy(
    user_id: uuid.UUID,
    db: AsyncSession,
) -> EmergencyPolicy | None:
    """
    Return the user's configured emergency policy, or None if not configured.

    BE2 INSTRUCTIONS:
        This function is already implemented with a real DB query.
        You may add caching or additional logic, but keep the signature.
    """
    result = await db.execute(
        select(EmergencyPolicy).where(EmergencyPolicy.user_id == user_id)
    )
    return result.scalar_one_or_none()


async def get_policy_or_default(
    user_id: uuid.UUID,
    db: AsyncSession,
) -> EmergencyPolicy:
    """
    Return the user's policy, or a safe default if not configured.

    The default is conservative: 30s timeout, notify primary only.
    BE2 may adjust the defaults.
    """
    from app.config import get_settings

    settings = get_settings()
    policy = await get_emergency_policy(user_id, db)
    if policy is not None:
        return policy

    # Return an in-memory default — not persisted, not tied to a user row
    default = EmergencyPolicy()
    default.user_id = user_id
    default.verification_timeout_seconds = settings.DEFAULT_VERIFICATION_TIMEOUT_SECONDS
    default.auto_escalate = True
    default.notify_primary_on_no_response = True
    default.notify_secondary_on_no_response = False
    default.share_location_on_escalation = True
    return default
