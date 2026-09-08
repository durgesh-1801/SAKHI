"""create emergency tables

Revision ID: 001
Revises: 
Create Date: 2026-09-08

Creates:
  - users (stub — BE1 will ADD COLUMN as needed)
  - trusted_contacts (stub — BE2 owns)
  - emergency_policies (stub — BE2 owns)
  - user_consents (stub — BE2 owns)
  - emergency_incidents (BE3 owns)
  - incident_events (BE3 owns)
  - incident_location_updates (BE3 owns)
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ─── Enum types ───────────────────────────────────────────────────────────
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE risk_level_enum AS ENUM ('SAFE', 'SUSPICIOUS', 'HIGH', 'CRITICAL');
        EXCEPTION WHEN duplicate_object THEN null;
        END $$;
    """)
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE incident_status_enum AS ENUM
                ('ACTIVE', 'VERIFYING', 'ESCALATING', 'RESOLVED', 'CANCELLED');
        EXCEPTION WHEN duplicate_object THEN null;
        END $$;
    """)
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE trigger_type_enum AS ENUM
                ('MANUAL_SOS', 'AI_DETECTION', 'FALL_DETECTION',
                 'DISTRESS_DETECTION', 'SAFE_JOURNEY', 'OTHER');
        EXCEPTION WHEN duplicate_object THEN null;
        END $$;
    """)
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE event_type_enum AS ENUM
                ('INCIDENT_CREATED', 'VERIFICATION_REQUESTED', 'USER_CONFIRMED_SAFE',
                 'USER_REQUESTED_HELP', 'NO_RESPONSE', 'CONTACT_NOTIFIED',
                 'LOCATION_SHARING_STARTED', 'LOCATION_UPDATED', 'ESCALATED',
                 'INCIDENT_RESOLVED', 'INCIDENT_CANCELLED', 'AI_TRIGGER_RECEIVED',
                 'CONSENT_DENIED');
        EXCEPTION WHEN duplicate_object THEN null;
        END $$;
    """)

    # ─── users (stub) ─────────────────────────────────────────────────────────
    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("full_name", sa.String(255), nullable=False),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("phone_number", sa.String(20), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("email"),
    )
    op.create_index("ix_users_email", "users", ["email"])

    # ─── trusted_contacts (stub) ──────────────────────────────────────────────
    op.create_table(
        "trusted_contacts",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("contact_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("phone_number", sa.String(20), nullable=True),
        sa.Column("email", sa.String(255), nullable=True),
        sa.Column("is_primary", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["contact_user_id"], ["users.id"], ondelete="SET NULL"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_trusted_contacts_user_id", "trusted_contacts", ["user_id"])

    # ─── emergency_policies (stub) ────────────────────────────────────────────
    op.create_table(
        "emergency_policies",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "verification_timeout_seconds", sa.Integer(), nullable=False, server_default="30"
        ),
        sa.Column("auto_escalate", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column(
            "notify_primary_on_no_response",
            sa.Boolean(),
            nullable=False,
            server_default="true",
        ),
        sa.Column(
            "notify_secondary_on_no_response",
            sa.Boolean(),
            nullable=False,
            server_default="false",
        ),
        sa.Column(
            "share_location_on_escalation",
            sa.Boolean(),
            nullable=False,
            server_default="true",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id"),
    )

    # ─── user_consents (stub) ─────────────────────────────────────────────────
    op.create_table(
        "user_consents",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "allow_location_sharing", sa.Boolean(), nullable=False, server_default="false"
        ),
        sa.Column(
            "allow_auto_escalation", sa.Boolean(), nullable=False, server_default="false"
        ),
        sa.Column(
            "allow_ai_monitoring", sa.Boolean(), nullable=False, server_default="false"
        ),
        sa.Column(
            "allow_audio_monitoring", sa.Boolean(), nullable=False, server_default="false"
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id"),
    )

    # ─── emergency_incidents (BE3) ────────────────────────────────────────────
    op.create_table(
        "emergency_incidents",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("trigger_type", sa.Enum(name="trigger_type_enum"), nullable=False),
        sa.Column(
            "status",
            sa.Enum(name="incident_status_enum"),
            nullable=False,
            server_default="ACTIVE",
        ),
        sa.Column(
            "risk_level",
            sa.Enum(name="risk_level_enum"),
            nullable=False,
            server_default="CRITICAL",
        ),
        sa.Column("risk_score", sa.Float(), nullable=True),
        sa.Column("latitude", sa.Float(), nullable=True),
        sa.Column("longitude", sa.Float(), nullable=True),
        sa.Column("location_accuracy", sa.Float(), nullable=True),
        sa.Column("location_updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("ai_reasons", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column(
            "policy_snapshot", postgresql.JSONB(astext_type=sa.Text()), nullable=True
        ),
        sa.Column("escalation_task_id", sa.String(255), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_emergency_incidents_user_id_status",
        "emergency_incidents",
        ["user_id", "status"],
    )
    op.create_index(
        "ix_emergency_incidents_status", "emergency_incidents", ["status"]
    )
    op.create_index(
        "ix_emergency_incidents_created_at", "emergency_incidents", ["created_at"]
    )
    op.create_index(
        "ix_emergency_incidents_user_id", "emergency_incidents", ["user_id"]
    )

    # ─── incident_events (BE3) ────────────────────────────────────────────────
    op.create_table(
        "incident_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("incident_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("event_type", sa.Enum(name="event_type_enum"), nullable=False),
        sa.Column("description", sa.String(1000), nullable=False),
        sa.Column("metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["incident_id"], ["emergency_incidents.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_incident_events_incident_id", "incident_events", ["incident_id"]
    )
    op.create_index("ix_incident_events_created_at", "incident_events", ["created_at"])

    # ─── incident_location_updates (BE3) ──────────────────────────────────────
    op.create_table(
        "incident_location_updates",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("incident_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("latitude", sa.Float(), nullable=False),
        sa.Column("longitude", sa.Float(), nullable=False),
        sa.Column("accuracy", sa.Float(), nullable=True),
        sa.Column(
            "recorded_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["incident_id"], ["emergency_incidents.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_location_updates_incident_id",
        "incident_location_updates",
        ["incident_id"],
    )
    op.create_index(
        "ix_location_updates_recorded_at",
        "incident_location_updates",
        ["recorded_at"],
    )


def downgrade() -> None:
    op.drop_table("incident_location_updates")
    op.drop_table("incident_events")
    op.drop_table("emergency_incidents")
    op.drop_table("user_consents")
    op.drop_table("emergency_policies")
    op.drop_table("trusted_contacts")
    op.drop_table("users")

    op.execute("DROP TYPE IF EXISTS event_type_enum")
    op.execute("DROP TYPE IF EXISTS trigger_type_enum")
    op.execute("DROP TYPE IF EXISTS incident_status_enum")
    op.execute("DROP TYPE IF EXISTS risk_level_enum")
