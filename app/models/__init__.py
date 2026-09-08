"""
app/models package
==================
Imports all models so that SQLAlchemy's metadata is fully populated
before Alembic or create_all is called.

⚠️ ADD NEW MODELS HERE when created.
"""

from app.database import Base  # noqa: F401

# ─── BE1 ZONE ──────────────────────────────────────────────────────────────
from app.models.user import User  # noqa: F401

# ─── BE2 ZONE ──────────────────────────────────────────────────────────────
from app.models.contact import TrustedContact  # noqa: F401
from app.models.policy import EmergencyPolicy  # noqa: F401
from app.models.consent import UserConsent  # noqa: F401

# ─── BE3 ZONE ──────────────────────────────────────────────────────────────
from app.models.emergency import (  # noqa: F401
    EmergencyIncident,
    IncidentEvent,
    IncidentLocationUpdate,
)
