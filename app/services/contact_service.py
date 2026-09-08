"""
ARIA / SAKHI — Contact Service
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
from typing import List, Optional
from sqlalchemy.orm import Session
from app.models.contact import TrustedContact
from app.models.policy import EmergencyPolicy
from app.schemas.contact import ContactCreate, ContactUpdate
from app.core.exceptions import EntityNotFoundException, ForbiddenException


class ContactService:
    @staticmethod
    def get_contact_for_user(db: Session, contact_id: str, user_id: str) -> TrustedContact:
        contact = db.query(TrustedContact).filter(TrustedContact.id == contact_id).first()
        if not contact:
            raise EntityNotFoundException("TrustedContact", contact_id)
        if contact.user_id != user_id:
            raise ForbiddenException("You do not have permission to access this contact")
        return contact

    @staticmethod
    def list_contacts(db: Session, user_id: str) -> List[TrustedContact]:
        return (
            db.query(TrustedContact)
            .filter(TrustedContact.user_id == user_id)
            .order_by(TrustedContact.priority.asc(), TrustedContact.created_at.asc())
            .all()
        )

    @staticmethod
    def create_contact(db: Session, user_id: str, contact_in: ContactCreate) -> TrustedContact:
        contact = TrustedContact(
            user_id=user_id,
            name=contact_in.name.strip(),
            phone=contact_in.phone.strip(),
            relationship_type=contact_in.relationship_type.strip() if contact_in.relationship_type else None,
            priority=contact_in.priority,
            verified=contact_in.verified
        )
        db.add(contact)
        db.commit()
        db.refresh(contact)
        return contact

    @staticmethod
    def update_contact(
        db: Session,
        contact_id: str,
        user_id: str,
        contact_in: ContactUpdate
    ) -> TrustedContact:
        contact = ContactService.get_contact_for_user(db, contact_id, user_id)

        if contact_in.name is not None:
            contact.name = contact_in.name.strip()
        if contact_in.phone is not None:
            contact.phone = contact_in.phone.strip()
        if contact_in.relationship_type is not None:
            contact.relationship_type = contact_in.relationship_type.strip()
        if contact_in.priority is not None:
            contact.priority = contact_in.priority
        if contact_in.verified is not None:
            contact.verified = contact_in.verified

        db.commit()
        db.refresh(contact)
        return contact

    @staticmethod
    def delete_contact(db: Session, contact_id: str, user_id: str) -> None:
        contact = ContactService.get_contact_for_user(db, contact_id, user_id)

        # Clean up references in EmergencyPolicy if referenced
        policy = db.query(EmergencyPolicy).filter(EmergencyPolicy.user_id == user_id).first()
        if policy:
            if policy.primary_contact_id == contact_id:
                policy.primary_contact_id = None
            if policy.secondary_contact_id == contact_id:
                policy.secondary_contact_id = None

        db.delete(contact)
        db.commit()


contact_service = ContactService()
