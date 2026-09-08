from sqlalchemy.orm import Session
from app.models.user import User
from app.schemas.context import AIRiskContext, EmergencyDispatchContext
from app.schemas.consent import ConsentResponse
from app.schemas.policy import PolicyResponse
from app.schemas.journey import JourneyResponse
from app.schemas.contact import ContactResponse
from app.services.user_service import user_service
from app.services.consent_service import consent_service
from app.services.policy_service import policy_service
from app.services.contact_service import contact_service
from app.services.journey_service import journey_service
from app.core.exceptions import EntityNotFoundException


class ContextService:
    @staticmethod
    def get_ai_risk_context(db: Session, user_id: str) -> AIRiskContext:
        """
        Supplies AI Risk Engine (Backend 1) with necessary user consent and journey status.
        Ensures AI models do not analyze user data without explicit consent.
        """
        user = user_service.get_by_id(db, user_id)
        if not user:
            raise EntityNotFoundException("User", user_id)

        consent = consent_service.get_or_create_consent(db, user_id)
        active_journey = journey_service.get_active_journey(db, user_id)

        return AIRiskContext(
            user_id=user.id,
            ai_detection_permitted=consent.ai_detection,
            audio_analysis_permitted=consent.audio_analysis,
            location_monitoring_permitted=consent.location_monitoring,
            active_journey=JourneyResponse.model_validate(active_journey) if active_journey else None,
            consent=ConsentResponse.model_validate(consent)
        )

    @staticmethod
    def get_emergency_dispatch_context(db: Session, user_id: str) -> EmergencyDispatchContext:
        """
        Supplies Emergency & Realtime (Backend 3) with pre-configured emergency policy,
        contacts ordered by priority, and user escalation preferences.
        """
        user = user_service.get_by_id(db, user_id)
        if not user:
            raise EntityNotFoundException("User", user_id)

        consent = consent_service.get_or_create_consent(db, user_id)
        policy = policy_service.get_or_create_policy(db, user_id)
        contacts = contact_service.list_contacts(db, user_id)
        active_journey = journey_service.get_active_journey(db, user_id)

        # Consent overrides policy: if location_monitoring consent is False, disable location sharing
        location_sharing = policy.location_sharing_enabled and consent.location_monitoring

        return EmergencyDispatchContext(
            user_id=user.id,
            user_name=user.name,
            user_phone=user.phone,
            auto_escalation_permitted=consent.automatic_escalation and policy.auto_alert_enabled,
            evidence_collection_permitted=consent.evidence_collection,
            verification_timeout=policy.verification_timeout,
            location_sharing_enabled=location_sharing,
            policy=PolicyResponse.model_validate(policy),
            consent=ConsentResponse.model_validate(consent),
            active_journey=JourneyResponse.model_validate(active_journey) if active_journey else None,
            recipients=[ContactResponse.model_validate(c) for c in contacts]
        )


context_service = ContextService()
