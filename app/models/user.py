import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, Boolean, DateTime
from sqlalchemy.orm import relationship
from app.database import Base


def generate_uuid() -> str:
    return str(uuid.uuid4())


def get_utc_now() -> datetime:
    return datetime.now(timezone.utc)


class User(Base):
    __tablename__ = "users"

    id = Column(String(36), primary_key=True, default=generate_uuid, index=True)
    name = Column(String(120), nullable=False)
    email = Column(String(255), unique=True, index=True, nullable=False)
    phone = Column(String(30), index=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime(timezone=True), default=get_utc_now, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=get_utc_now, onupdate=get_utc_now, nullable=False)

    # Relationships
    contacts = relationship("TrustedContact", back_populates="user", cascade="all, delete-orphan", order_by="TrustedContact.priority")
    consent = relationship("UserConsent", back_populates="user", uselist=False, cascade="all, delete-orphan")
    emergency_policy = relationship("EmergencyPolicy", back_populates="user", uselist=False, cascade="all, delete-orphan")
    journeys = relationship("SafeJourney", back_populates="user", cascade="all, delete-orphan", order_by="desc(SafeJourney.created_at)")
