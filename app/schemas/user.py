"""
ARIA / SAKHI — User Schemas
============================
⚠️  BE1 ZONE — Minimal stub so BE3's auth dependency compiles.
    BE1 should expand this with all required user fields.
"""

from uuid import UUID
from pydantic import BaseModel, EmailStr


class UserRead(BaseModel):
    """
    Read-only view of a user returned by the auth dependency.

    BE1 INSTRUCTIONS:
        Add all fields that the authenticated user object should expose.
        BE3 only reads: id, full_name, phone_number (for notifications).
        Do not remove these three fields — BE3 depends on them.
    """

    id: UUID
    full_name: str
    email: EmailStr
    phone_number: str | None = None  # Used by BE3 for SMS notifications

    model_config = {"from_attributes": True}
