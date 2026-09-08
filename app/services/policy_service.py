"""
ARIA / SAKHI — Policy Service
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
    result = await db.execute(select(EmergencyPolicy).where(EmergencyPolicy.user_id == user_id))
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

    # Return an in-memohttps://github.com/durgesh-1801/SAKHI/pull/4/conflict?name=app%252Fservices%252Fpolicy_service.py&base_oid=49e773990f31cebb401685f519d25658684e47fd&head_oid=5abc80e96f5641c1480ef6fa82020e9c458b5086ry default — not persisted, not tied to a user row
    default = EmergencyPolicy()
    default.user_id = user_id
    default.verification_timeout_seconds = settings.DEFAULT_VERIFICATION_TIMEOUT_SECONDS
    default.auto_escalate = True
    default.notify_primary_on_no_response = True
    default.notify_secondary_on_no_response = False
    default.share_location_on_escalation = True
    return default
from typing import Optional
from sqlalchemy.orm import Session
from app.models.policy import EmergencyPolicy
from app.models.contact import TrustedContact
from app.schemas.policy import PolicyUpdate
from app.core.exceptions import BadRequestException


class PolicyService:
    @staticmethod
    def get_or_create_policy(db: Session, user_id: str) -> EmergencyPolicy:
        policy = db.query(EmergencyPolicy).filter(EmergencyPolicy.user_id == user_id).first()
        if not policy:
            policy = EmergencyPolicy(
                user_id=user_id,
                verification_timeout=30,
                auto_alert_enabled=True,
                location_sharing_enabled=True,
                primary_contact_id=None,
                secondary_contact_id=None,
                escalation_level=1
            )
            db.add(policy)
            db.commit()
            db.refresh(policy)
        return policy

    @staticmethod
    def validate_contact_ownership(db: Session, contact_id: Optional[str], user_id: str, label: str) -> None:
        if contact_id is None or contact_id == "":
            return
        contact = db.query(TrustedContact).filter(TrustedContact.id == contact_id).first()
        if not contact:
            raise BadRequestException(f"Specified {label} contact '{contact_id}' does not exist")
        if contact.user_id != user_id:
            raise BadRequestException(f"Specified {label} contact does not belong to your account")

    @staticmethod
    def update_policy(db: Session, user_id: str, policy_in: PolicyUpdate) -> EmergencyPolicy:
        policy = PolicyService.get_or_create_policy(db, user_id)

        if "primary_contact_id" in policy_in.model_fields_set:
            if policy_in.primary_contact_id:
                PolicyService.validate_contact_ownership(db, policy_in.primary_contact_id, user_id, "primary")
                policy.primary_contact_id = policy_in.primary_contact_id
            else:
                policy.primary_contact_id = None

        if "secondary_contact_id" in policy_in.model_fields_set:
            if policy_in.secondary_contact_id:
                PolicyService.validate_contact_ownership(db, policy_in.secondary_contact_id, user_id, "secondary")
                policy.secondary_contact_id = policy_in.secondary_contact_id
            else:
                policy.secondary_contact_id = None

        # Prevent assigning the exact same contact as both primary and secondary
        if (
            policy.primary_contact_id is not None
            and policy.secondary_contact_id is not None
            and policy.primary_contact_id == policy.secondary_contact_id
        ):
            raise BadRequestException("Primary and secondary emergency contacts must be distinct")

        if policy_in.verification_timeout is not None:
            if not (10 <= policy_in.verification_timeout <= 300):
                raise BadRequestException("Verification timeout must be between 10 and 300 seconds")
            policy.verification_timeout = policy_in.verification_timeout

        if policy_in.auto_alert_enabled is not None:
            policy.auto_alert_enabled = policy_in.auto_alert_enabled

        if policy_in.location_sharing_enabled is not None:
            policy.location_sharing_enabled = policy_in.location_sharing_enabled

        if policy_in.escalation_level is not None:
            if not (1 <= policy_in.escalation_level <= 3):
                raise BadRequestException("Escalation level must be between 1 and 3")
            policy.escalation_level = policy_in.escalation_level

        db.commit()
        db.refresh(policy)
        return policy


policy_service = PolicyService()
