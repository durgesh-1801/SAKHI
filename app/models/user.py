"""
ARIA / SAKHI — User Model
==========================
⚠️  BE1 ZONE — Minimal stub so ForeignKey references compile.
    BE1 should expand this with all required user fields (hashed_password, etc.).
    DO NOT add emergency columns here — those belong to emergency.py.
"""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class User(Base):
    """
    Application user.

    BE1 INSTRUCTIONS:
        Expand this model with your required fields.
        Keep `id`, `full_name`, `email`, `phone_number` — BE3 reads them.
        Do not rename the table `users` without coordinating with BE3.
    """

    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
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
    )

    # ─── BE3 back-references ─────────────────────────────────────────────────
    emergency_incidents: Mapped[list["EmergencyIncident"]] = relationship(  # type: ignore[name-defined]
        "EmergencyIncident", back_populates="user", lazy="noload"
    )

    def __repr__(self) -> str:
        return f"<User id={self.id} email={self.email}>"
