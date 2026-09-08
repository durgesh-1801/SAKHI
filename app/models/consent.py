import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, Boolean, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from app.database import Base


def generate_uuid() -> str:
    return str(uuid.uuid4())


def get_utc_now() -> datetime:
    return datetime.now(timezone.utc)


class UserConsent(Base):
    __tablename__ = "user_consents"

    id = Column(String(36), primary_key=True, default=generate_uuid, index=True)
    user_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False, index=True)
    
    # Granular Consent Toggles (Consent-first: explicit opt-in)
    location_monitoring = Column(Boolean, default=False, nullable=False)
    ai_detection = Column(Boolean, default=False, nullable=False)
    audio_analysis = Column(Boolean, default=False, nullable=False)
    automatic_escalation = Column(Boolean, default=False, nullable=False)
    evidence_collection = Column(Boolean, default=False, nullable=False)

    created_at = Column(DateTime(timezone=True), default=get_utc_now, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=get_utc_now, onupdate=get_utc_now, nullable=False)

    # Relationships
    user = relationship("User", back_populates="consent")
