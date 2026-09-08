"""
ARIA / SAKHI — User Model
⚠️  BE1 ZONE — Minimal stub so ForeignKey references compile.
    BE1 should expand this with all required user fields (hashed_password, etc.).
    DO NOT add emergency columns here — those belong to emergency.py.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.models.emergency import EmergencyIncident

from sqlalchemy import DateTime, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import GUID, Base


class User(Base):
    """
    Application user.

    BE1 INSTRUCTIONS:
        Expand this model with your required fields.
        Keep `id`, `full_name`, `email`, `phone_number` — BE3 reads them.
        Do not rename the table `users` without coordinating with BE3.
    """

    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(GUID, primary_key=True, default=uuid.uuid4)
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    phone_number: Mapped[str | None] = mapped_column(String(20), nullable=True)
    # BE1 adds: hashed_password, is_active, is_verified, fcm_token, etc.

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )https://github.com/durgesh-1801/SAKHI/pull/4/conflict?name=app%252Fmodels%252Fuser.py&base_oid=76c350b4c5f818bc61dc078383cbe748a6cf1eab&head_oid=3293c72e480e8e8e09909bb117f76633d6c75e3f

    # ─── BE3 back-references ─────────────────────────────────────────────────
    emergency_incidents: Mapped[list[EmergencyIncident]] = relationship(
        "EmergencyIncident", back_populates="user", lazy="noload"
    )

    def __repr__(self) -> str:
        return f"<User id={self.id} email={self.email}>"
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
