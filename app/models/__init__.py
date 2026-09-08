"""
app/models package
Imports all models so that SQLAlchemy's metadata is fully populated
before Alembic or create_all is called.

⚠️ ADD NEW MODELS HERE when created.
"""

from app.database import Base  # noqa: F401
from app.models.consent import UserConsent  # noqa: F401

# ─── BE2 ZONE ──────────────────────────────────────────────────────────────
from app.models.contact import TrustedContact  # noqa: F401

# ─── BE3 ZONE ──────────────────────────────────────────────────────────────
from app.models.emergency import (  # noqa: F401
    EmergencyIncident,
    IncidentEvent,
    IncidentLocationUpdate,
)
from app.models.policy import EmergencyPolicy  # noqa: F401

# ─── BE1 ZONE ──────────────────────────────────────────────────────────────
from app.models.user import User  # noqa: F401

__all__ = [
    "Base",
    "EmergencyIncident",
    "EmergencyPolicy",
    "IncidentEvent",
    "IncidentLocationUpdate",
    "TrustedContact",
    "User",
    "UserConsent",
from app.database import Base
from app.models.user import User
from app.models.contact import TrustedContact
from app.models.consent import UserConsent
from app.models.policy import EmergencyPolicy
from app.models.journey import SafeJourney, JourneyStatus

__all__ = [
    "Base",
    "User",
    "TrustedContact",
    "UserConsent",
    "EmergencyPolicy",
    "SafeJourney",
    "JourneyStatus",
]
