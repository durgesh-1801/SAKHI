"""
ARIA / SAKHI — Trusted Contact Model
======================================
⚠️  BE2 ZONE — Minimal stub for FK references and notification targeting.
    BE2 should expand this with all contact fields (relationship type, etc.).
"""

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class TrustedContact(Base):
    """
    A person trusted by the user to receive emergency alerts.

    BE2 INSTRUCTIONS:
        Expand this with all fields required for contact management.
        Keep `id`, `user_id`, `contact_user_id`, `name`, `phone_number`,
        `email`, `is_primary` — BE3 reads these for notification targeting
        and guardian WebSocket authorization.
        Do not rename the table `trusted_contacts`.
    """

    __tablename__ = "trusted_contacts"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    # If the contact is also a SAKHI user, link their account
    contact_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    phone_number: Mapped[str | None] = mapped_column(String(20), nullable=True)
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    is_primary: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    # BE2 adds: relationship_type, fcm_token, notification_preferences, etc.

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    # Relationships
    user: Mapped["User"] = relationship(  # type: ignore[name-defined]
        "User", foreign_keys=[user_id], lazy="noload"
    )

    def __repr__(self) -> str:
        return f"<TrustedContact id={self.id} user_id={self.user_id} name={self.name}>"
