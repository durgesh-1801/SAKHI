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
