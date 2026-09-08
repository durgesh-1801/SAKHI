"""
ARIA / SAKHI — User Consent Model
===================================
⚠️  BE2 ZONE — Minimal stub. BE2 owns full CRUD.
    BE3 checks consent flags before taking any action that
    involves the user's data (location sharing, escalation).

    KEY FIELDS BE3 READS:
        - allow_location_sharing     → gate for live location broadcast
        - allow_auto_escalation      → gate for automatic escalation
        - allow_ai_monitoring        → gate for acting on AI risk results
        - allow_audio_monitoring     → informational (not directly used by BE3)
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.models.user import User

from sqlalchemy import Boolean, DateTime, ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import GUID, Base


class UserConsent(Base):
    """
    User consent flags.

    BE2 INSTRUCTIONS:
        Expand with all consent options.
        Keep the four fields listed above — BE3 reads them as gates.
        Do not rename the table `user_consents`.
    """

    __tablename__ = "user_consents"

    id: Mapped[uuid.UUID] = mapped_column(GUID, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        GUID,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )

    # BE3 reads these as gates before any emergency action
    allow_location_sharing: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    allow_auto_escalation: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    allow_ai_monitoring: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    allow_audio_monitoring: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    # BE2 adds: granular permissions, last_updated_by_user, etc.

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
        return f"<UserConsent user_id={self.user_id}>"
