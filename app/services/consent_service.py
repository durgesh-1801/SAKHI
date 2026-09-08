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
