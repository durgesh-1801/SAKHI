"""
ARIA / SAKHI — Contact Service
================================
⚠️  BE2 ZONE — BE3 calls these functions for notification targeting
    and guardian WebSocket authorization.
    BE2 owns full CRUD — BE3 only reads.

BE3 CONTRACT (do not change function signatures):
    get_trusted_contacts(user_id, db) -> list[TrustedContact]
    get_primary_contacts(user_id, db) -> list[TrustedContact]
    is_trusted_contact(guardian_user_id, incident_user_id, db) -> bool
"""

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.contact import TrustedContact


async def get_trusted_contacts(
    user_id: uuid.UUID,
    db: AsyncSession,
) -> list[TrustedContact]:
    """Return all trusted contacts for a user."""
    result = await db.execute(
        select(TrustedContact)
        .where(TrustedContact.user_id == user_id)
        .order_by(TrustedContact.is_primary.desc())
    )
    return list(result.scalars().all())


async def get_primary_contacts(
    user_id: uuid.UUID,
    db: AsyncSession,
) -> list[TrustedContact]:
    """Return only primary trusted contacts for a user."""
    result = await db.execute(
        select(TrustedContact).where(
            TrustedContact.user_id == user_id,
            TrustedContact.is_primary.is_(True),
        )
    )
    return list(result.scalars().all())


async def is_trusted_contact(
    guardian_user_id: uuid.UUID,
    incident_user_id: uuid.UUID,
    db: AsyncSession,
) -> bool:
    """
    Returns True if `guardian_user_id` is a trusted contact of `incident_user_id`.
    Used by BE3 to authorize guardian WebSocket connections and location requests.
    """
    result = await db.execute(
        select(TrustedContact).where(
            TrustedContact.user_id == incident_user_id,
            TrustedContact.contact_user_id == guardian_user_id,
        )
    )
    return result.scalar_one_or_none() is not None
