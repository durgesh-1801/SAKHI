import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, Boolean, Integer, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from app.database import Base


def generate_uuid() -> str:
    return str(uuid.uuid4())


def get_utc_now() -> datetime:
    return datetime.now(timezone.utc)


class EmergencyPolicy(Base):
    __tablename__ = "emergency_policies"

    id = Column(String(36), primary_key=True, default=generate_uuid, index=True)
    user_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False, index=True)
    
    # Policy Configurations
    verification_timeout = Column(Integer, default=30, nullable=False)  # in seconds (e.g. 10 to 300)
    auto_alert_enabled = Column(Boolean, default=True, nullable=False)
    location_sharing_enabled = Column(Boolean, default=True, nullable=False)
    
    primary_contact_id = Column(String(36), ForeignKey("trusted_contacts.id", ondelete="SET NULL"), nullable=True)
    secondary_contact_id = Column(String(36), ForeignKey("trusted_contacts.id", ondelete="SET NULL"), nullable=True)
    
    escalation_level = Column(Integer, default=1, nullable=False)  # 1 = Primary, 2 = Both, 3 = All + Authorities

    created_at = Column(DateTime(timezone=True), default=get_utc_now, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=get_utc_now, onupdate=get_utc_now, nullable=False)

    # Relationships
    user = relationship("User", back_populates="emergency_policy")
    primary_contact = relationship("TrustedContact", foreign_keys=[primary_contact_id], lazy="joined")
    secondary_contact = relationship("TrustedContact", foreign_keys=[secondary_contact_id], lazy="joined")
