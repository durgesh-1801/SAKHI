"""
ARIA / SAKHI — Test Configuration & Fixtures
==============================================
Provides:
  - In-memory SQLite async DB for tests (no PostgreSQL required)
  - Async test client (httpx)
  - Authenticated user fixture (bypasses BE1 auth stub)
  - Helper fixtures for incidents, contacts, policy
"""

import asyncio
import uuid
from collections.abc import AsyncGenerator
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.database import Base, get_db
from app.main import app
from app.schemas.user import UserRead

# ── In-memory test database ───────────────────────────────────────────────────
TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"

test_engine = create_async_engine(
    TEST_DATABASE_URL,
    connect_args={"check_same_thread": False},
    echo=False,
)

TestSessionLocal = async_sessionmaker(
    bind=test_engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)


@pytest_asyncio.fixture(scope="session")
async def setup_test_db():
    """Create all tables once per test session."""
    async with test_engine.begin() as conn:
        # SQLite doesn't support PostgreSQL enums — use String for enum columns
        # The models use Enum(name=...) which SQLite stores as VARCHAR
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest_asyncio.fixture
async def db_session(setup_test_db) -> AsyncGenerator[AsyncSession, None]:
    """Provide a fresh async DB session per test, rolled back on completion."""
    async with TestSessionLocal() as session:
        yield session
        await session.rollback()


@pytest_asyncio.fixture
async def client(db_session: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    """
    Async test client with:
      - Test DB injected via dependency override
      - Auth bypassed with a fixed test user
    """
    # Override DB dependency
    async def override_get_db() -> AsyncGenerator[AsyncSession, None]:
        yield db_session

    # Override auth dependency — returns a fixed test user
    from app.auth.dependencies import get_current_user

    test_user = UserRead(
        id=TEST_USER_ID,
        full_name="Test User",
        email="test@aria.app",
        phone_number="+911234567890",
    )

    async def override_get_current_user(token: str = "") -> UserRead:
        return test_user

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user] = override_get_current_user

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac

    app.dependency_overrides.clear()


# ── Shared test constants ──────────────────────────────────────────────────────

TEST_USER_ID = uuid.UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
TEST_GUARDIAN_ID = uuid.UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb")
TEST_INCIDENT_ID = uuid.UUID("cccccccc-cccc-cccc-cccc-cccccccccccc")


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest_asyncio.fixture
async def test_user(db_session: AsyncSession) -> Any:
    """Insert a test user row."""
    from app.models.user import User

    user = User(
        id=TEST_USER_ID,
        full_name="Test User",
        email="test@aria.app",
        phone_number="+911234567890",
    )
    db_session.add(user)
    await db_session.flush()
    return user


@pytest_asyncio.fixture
async def test_contact(db_session: AsyncSession, test_user: Any) -> Any:
    """Insert a primary trusted contact for the test user."""
    from app.models.contact import TrustedContact

    contact = TrustedContact(
        id=uuid.uuid4(),
        user_id=TEST_USER_ID,
        contact_user_id=TEST_GUARDIAN_ID,
        name="Guardian User",
        phone_number="+910987654321",
        email="guardian@aria.app",
        is_primary=True,
    )
    db_session.add(contact)
    await db_session.flush()
    return contact


@pytest_asyncio.fixture
async def test_policy(db_session: AsyncSession, test_user: Any) -> Any:
    """Insert a test emergency policy for the user."""
    from app.models.policy import EmergencyPolicy

    policy = EmergencyPolicy(
        id=uuid.uuid4(),
        user_id=TEST_USER_ID,
        verification_timeout_seconds=10,
        auto_escalate=True,
        notify_primary_on_no_response=True,
        notify_secondary_on_no_response=False,
        share_location_on_escalation=True,
    )
    db_session.add(policy)
    await db_session.flush()
    return policy


@pytest_asyncio.fixture
async def test_consent(db_session: AsyncSession, test_user: Any) -> Any:
    """Insert consent record with all permissions enabled."""
    from app.models.consent import UserConsent

    consent = UserConsent(
        id=uuid.uuid4(),
        user_id=TEST_USER_ID,
        allow_location_sharing=True,
        allow_auto_escalation=True,
        allow_ai_monitoring=True,
        allow_audio_monitoring=False,
    )
    db_session.add(consent)
    await db_session.flush()
    return consent


@pytest_asyncio.fixture
async def active_incident(db_session: AsyncSession, test_user: Any) -> Any:
    """Insert an active emergency incident for the test user."""
    from app.models.emergency import EmergencyIncident

    incident = EmergencyIncident(
        id=TEST_INCIDENT_ID,
        user_id=TEST_USER_ID,
        trigger_type="MANUAL_SOS",
        status="ACTIVE",
        risk_level="CRITICAL",
        latitude=26.8432,
        longitude=75.5651,
    )
    db_session.add(incident)
    await db_session.flush()
    return incident


@pytest_asyncio.fixture
async def verifying_incident(db_session: AsyncSession, test_user: Any) -> Any:
    """Insert an incident in VERIFYING status with a fake Celery task ID."""
    from app.models.emergency import EmergencyIncident

    incident = EmergencyIncident(
        id=uuid.uuid4(),
        user_id=TEST_USER_ID,
        trigger_type="AI_DETECTION",
        status="VERIFYING",
        risk_level="HIGH",
        risk_score=72.0,
        ai_reasons=["Abnormal movement detected"],
        escalation_task_id="fake-celery-task-id",
    )
    db_session.add(incident)
    await db_session.flush()
    return incident
