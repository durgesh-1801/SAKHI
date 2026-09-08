"""
Tests: Security — Authorization & Ownership
=============================================
Covers:
  - Unauthorized user cannot access another user's incident
  - Unauthorized user cannot access location endpoint
  - Guardian CAN access location endpoint
  - Non-guardian cannot access location endpoint
  - Already-resolved incident cannot be cancelled
"""

import uuid
from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient

from tests.conftest import TEST_USER_ID, TEST_GUARDIAN_ID


@pytest.mark.asyncio
async def test_cannot_access_other_users_incident(
    client: AsyncClient,
    db_session,
    test_user,
):
    """A user cannot read another user's incident."""
    from app.models.emergency import EmergencyIncident
    from app.models.user import User

    other_user = User(id=uuid.uuid4(), full_name="Other", email="other2@aria.app")
    db_session.add(other_user)
    await db_session.flush()

    incident = EmergencyIncident(
        id=uuid.uuid4(),
        user_id=other_user.id,
        trigger_type="MANUAL_SOS",
        status="ACTIVE",
        risk_level="CRITICAL",
    )
    db_session.add(incident)
    await db_session.flush()

    response = await client.get(f"/emergency/incidents/{incident.id}")
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_cannot_cancel_other_users_incident(
    client: AsyncClient,
    db_session,
    test_user,
):
    """A user cannot cancel another user's incident."""
    from app.models.emergency import EmergencyIncident
    from app.models.user import User

    other_user = User(id=uuid.uuid4(), full_name="Other", email="other3@aria.app")
    db_session.add(other_user)
    await db_session.flush()

    incident = EmergencyIncident(
        id=uuid.uuid4(),
        user_id=other_user.id,
        trigger_type="MANUAL_SOS",
        status="ACTIVE",
        risk_level="CRITICAL",
    )
    db_session.add(incident)
    await db_session.flush()

    response = await client.post(f"/emergency/incidents/{incident.id}/cancel")
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_location_endpoint_owner_access(
    client: AsyncClient,
    test_user,
    active_incident,
):
    """Incident owner can access location endpoint."""
    from tests.conftest import TEST_INCIDENT_ID

    response = await client.get(f"/emergency/incidents/{TEST_INCIDENT_ID}/location")
    assert response.status_code == 200
    body = response.json()
    assert body["incident_id"] == str(TEST_INCIDENT_ID)


@pytest.mark.asyncio
async def test_location_endpoint_guardian_access(
    client: AsyncClient,
    db_session,
    test_user,
    active_incident,
    test_contact,
):
    """
    A trusted guardian can access the location endpoint.
    Override auth to return guardian user.
    """
    from app.auth.dependencies import get_current_user
    from app.schemas.user import UserRead
    from app.database import get_db
    from tests.conftest import TEST_INCIDENT_ID

    guardian_user = UserRead(
        id=TEST_GUARDIAN_ID,
        full_name="Guardian User",
        email="guardian@aria.app",
    )

    async def guardian_auth(token: str = "") -> UserRead:
        return guardian_user

    async def override_db():
        yield db_session

    app_instance = client._transport.app  # type: ignore[attr-defined]
    app_instance.dependency_overrides[get_current_user] = guardian_auth
    app_instance.dependency_overrides[get_db] = override_db

    response = await client.get(f"/emergency/incidents/{TEST_INCIDENT_ID}/location")

    app_instance.dependency_overrides.clear()
    # Re-add default overrides so other tests still work
    # (fixture teardown handles this)

    assert response.status_code == 200


@pytest.mark.asyncio
async def test_location_endpoint_non_guardian_denied(
    client: AsyncClient,
    db_session,
    test_user,
    active_incident,
):
    """A random user who is not a trusted contact cannot access location."""
    from app.auth.dependencies import get_current_user
    from app.schemas.user import UserRead
    from app.database import get_db
    from tests.conftest import TEST_INCIDENT_ID

    random_user = UserRead(
        id=uuid.uuid4(),
        full_name="Random",
        email="random@aria.app",
    )

    async def random_auth(token: str = "") -> UserRead:
        return random_user

    async def override_db():
        yield db_session

    app_instance = client._transport.app  # type: ignore[attr-defined]
    app_instance.dependency_overrides[get_current_user] = random_auth
    app_instance.dependency_overrides[get_db] = override_db

    response = await client.get(f"/emergency/incidents/{TEST_INCIDENT_ID}/location")

    app_instance.dependency_overrides.clear()

    assert response.status_code == 403


@pytest.mark.asyncio
async def test_cannot_cancel_resolved_incident(
    client: AsyncClient,
    test_user,
    db_session,
):
    """Cancelling an already-RESOLVED incident → 409 Conflict."""
    from app.models.emergency import EmergencyIncident
    from datetime import datetime, timezone

    resolved = EmergencyIncident(
        id=uuid.uuid4(),
        user_id=TEST_USER_ID,
        trigger_type="MANUAL_SOS",
        status="RESOLVED",
        risk_level="CRITICAL",
        resolved_at=datetime.now(timezone.utc),
    )
    db_session.add(resolved)
    await db_session.flush()

    response = await client.post(f"/emergency/incidents/{resolved.id}/cancel")
    assert response.status_code == 409
