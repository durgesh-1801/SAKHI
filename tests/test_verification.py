"""
Tests: Verification Flow
=========================
Covers:
  - USER_CONFIRMED_SAFE → incident CANCELLED, escalation task revoked
  - USER_REQUESTED_HELP → escalation immediately triggered
  - Invalid response → 422
"""

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import AsyncClient

from tests.conftest import TEST_USER_ID


@pytest.mark.asyncio
async def test_user_confirmed_safe(
    client: AsyncClient,
    test_user,
    verifying_incident,
    db_session,
):
    """Responding USER_CONFIRMED_SAFE → incident becomes CANCELLED."""
    incident_id = str(verifying_incident.id)

    with patch(
        "app.services.verification_service._revoke_escalation_task"
    ) as mock_revoke, patch(
        "app.websocket.manager.ws_manager.broadcast_to_incident",
        new_callable=AsyncMock,
    ):
        response = await client.post(
            f"/emergency/incidents/{incident_id}/verify",
            json={"response": "USER_CONFIRMED_SAFE"},
        )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "CANCELLED"
    mock_revoke.assert_called_once_with("fake-celery-task-id")


@pytest.mark.asyncio
async def test_user_requested_help(
    client: AsyncClient,
    test_user,
    verifying_incident,
    test_contact,
    test_policy,
    test_consent,
):
    """Responding USER_REQUESTED_HELP → escalation executes."""
    incident_id = str(verifying_incident.id)

    with patch(
        "app.services.verification_service._revoke_escalation_task"
    ), patch(
        "app.services.escalation_service.execute_escalation",
        new_callable=AsyncMock,
        return_value=verifying_incident,
    ) as mock_escalate:
        response = await client.post(
            f"/emergency/incidents/{incident_id}/verify",
            json={"response": "USER_REQUESTED_HELP"},
        )

    assert response.status_code == 200
    mock_escalate.assert_called_once()


@pytest.mark.asyncio
async def test_verify_invalid_response(
    client: AsyncClient,
    test_user,
    verifying_incident,
):
    """Invalid verify response → 422."""
    incident_id = str(verifying_incident.id)
    response = await client.post(
        f"/emergency/incidents/{incident_id}/verify",
        json={"response": "MAYBE"},
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_verify_wrong_owner(
    client: AsyncClient,
    db_session,
    test_user,
):
    """Another user's incident → 403 (ownership check)."""
    from app.models.emergency import EmergencyIncident
    from app.models.user import User

    # Create a different user's incident
    other_user = User(
        id=uuid.uuid4(),
        full_name="Other User",
        email="other@aria.app",
    )
    db_session.add(other_user)
    await db_session.flush()

    other_incident = EmergencyIncident(
        id=uuid.uuid4(),
        user_id=other_user.id,
        trigger_type="MANUAL_SOS",
        status="VERIFYING",
        risk_level="CRITICAL",
    )
    db_session.add(other_incident)
    await db_session.flush()

    response = await client.post(
        f"/emergency/incidents/{other_incident.id}/verify",
        json={"response": "USER_CONFIRMED_SAFE"},
    )
    # Current user (TEST_USER_ID) doesn't own this incident → 403
    assert response.status_code == 403
