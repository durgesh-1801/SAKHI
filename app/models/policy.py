"""
ARIA / SAKHI — Emergency Policy Model
⚠️  BE2 ZONE — Minimal stub. BE2 owns full CRUD.
    BE3 reads this model to execute the escalation policy.

    KEY FIELDS BE3 READS:
        - verification_timeout_seconds   → how long to wait for user response
        - notify_primary_on_no_response  → should primary contact be notified on timeout?
        - notify_secondary_on_no_response→ should secondary contact also be notified?
        - share_location_on_escalation   → should live location be shared?
        - auto_escalate                  → should escalation happen without user confirmation?
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.models.user import User

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import GUID, Base


class EmergencyPolicy(Base):
    """
    User-configured emergency response policy.

    BE2 INSTRUCTIONS:
        Expand with all policy configuration options.
        Keep all fields listed below — BE3 reads them during escalation.
        Do not rename the table `emergency_policies`.
    """

    __tablename__ = "emergency_policies"

    id: Mapped[uuid.UUID] = mapped_column(GUID, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        GUID,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )

    # ─── Verification ─────────────────────────────────────────────────────
    # How many seconds to wait for user verification before auto-escalating
    verification_timeout_seconds: Mapped[int] = mapped_column(Integer, nullable=False, default=30)

    # ─── Escalation behaviour ─────────────────────────────────────────────
    # Whether BE3 should automatically escalate on no response
    auto_escalate: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    # Whether to notify the primary contact
    notify_primary_on_no_response: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True
    )

    # Whether to notify secondary contacts
    notify_secondary_on_no_response: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False
    )

    # Whether to share live location with contacts
    share_location_on_escalation: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True
    )

    # BE2 adds: minimum risk threshold for auto-escalation, notification channels, etc.

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    user: Mapped[User] = relationship("User", lazy="noload")

    def __repr__(self) -> str:
        return (
            f"<EmergencyPolicy user_id={self.user_id} timeout={self.verification_timeout_seconds}s>"
        )
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
