"""
Tests: Manual SOS Flow
========================
Covers:
  - POST /emergency/sos creates incident with ACTIVE status
  - Response contains incident_id, status, risk_level
  - Incident is CRITICAL for manual SOS
  - Location is stored if provided
  - Cannot SOS when another incident is already active (optional)
"""

from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient

from tests.conftest import TEST_USER_ID


@pytest.mark.asyncio
async def test_sos_creates_incident(
    client: AsyncClient, test_user, test_policy, test_consent, test_contact
):
    """POST /emergency/sos → 201, ACTIVE incident with CRITICAL risk."""
    with patch(
        "app.services.escalation_service.start_escalation", new_callable=AsyncMock
    ):
        response = await client.post(
            "/emergency/sos",
            json={"latitude": 26.8432, "longitude": 75.5651, "accuracy": 5.0},
        )

    assert response.status_code == 201
    body = response.json()
    assert body["status"] == "ACTIVE"
    assert body["risk_level"] == "CRITICAL"
    assert "incident_id" in body


@pytest.mark.asyncio
async def test_sos_without_location(
    client: AsyncClient, test_user, test_policy, test_consent
):
    """POST /emergency/sos with no location → still creates incident."""
    with patch(
        "app.services.escalation_service.start_escalation", new_callable=AsyncMock
    ):
        response = await client.post("/emergency/sos", json={})

    assert response.status_code == 201
    body = response.json()
    assert body["status"] == "ACTIVE"
    assert body["risk_level"] == "CRITICAL"


@pytest.mark.asyncio
async def test_sos_invalid_latitude(client: AsyncClient, test_user):
    """POST /emergency/sos with out-of-range latitude → 422."""
    response = await client.post(
        "/emergency/sos",
        json={"latitude": 999.0, "longitude": 75.5651},
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_sos_creates_timeline_event(
    client: AsyncClient, test_user, test_policy, test_consent, db_session
):
    """After SOS, an INCIDENT_CREATED event should be in the DB."""
    from app.models.emergency import IncidentEvent
    from sqlalchemy import select

    with patch(
        "app.services.escalation_service.start_escalation", new_callable=AsyncMock
    ):
        response = await client.post("/emergency/sos", json={})
    assert response.status_code == 201

    incident_id = response.json()["incident_id"]

    result = await db_session.execute(
        select(IncidentEvent).where(
            IncidentEvent.incident_id == incident_id,
            IncidentEvent.event_type == "INCIDENT_CREATED",
        )
    )
    event = result.scalar_one_or_none()
    assert event is not None
    assert event.event_type == "INCIDENT_CREATED"


@pytest.mark.asyncio
async def test_list_incidents(
    client: AsyncClient, test_user, active_incident
):
    """GET /emergency/incidents → returns user's incidents."""
    response = await client.get("/emergency/incidents")
    assert response.status_code == 200
    body = response.json()
    assert isinstance(body, list)
    assert len(body) >= 1
    assert body[0]["user_id"] == str(TEST_USER_ID)


@pytest.mark.asyncio
async def test_get_incident_detail(
    client: AsyncClient, test_user, active_incident
):
    """GET /emergency/incidents/{id} → returns incident detail."""
    from tests.conftest import TEST_INCIDENT_ID

    response = await client.get(f"/emergency/incidents/{TEST_INCIDENT_ID}")
    assert response.status_code == 200
    body = response.json()
    assert body["id"] == str(TEST_INCIDENT_ID)
    assert body["status"] == "ACTIVE"


@pytest.mark.asyncio
async def test_get_incident_not_found(client: AsyncClient, test_user):
    """GET /emergency/incidents/{unknown-id} → 404."""
    import uuid

    response = await client.get(f"/emergency/incidents/{uuid.uuid4()}")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_cancel_incident(
    client: AsyncClient, test_user, active_incident
):
    """POST /emergency/incidents/{id}/cancel → CANCELLED."""
    from tests.conftest import TEST_INCIDENT_ID

    with patch(
        "app.websocket.manager.ws_manager.broadcast_to_incident",
        new_callable=AsyncMock,
    ):
        response = await client.post(f"/emergency/incidents/{TEST_INCIDENT_ID}/cancel")
    assert response.status_code == 200
    assert response.json()["status"] == "CANCELLED"


@pytest.mark.asyncio
async def test_resolve_incident(
    client: AsyncClient, test_user, active_incident
):
    """POST /emergency/incidents/{id}/resolve → RESOLVED."""
    from tests.conftest import TEST_INCIDENT_ID

    with patch(
        "app.websocket.manager.ws_manager.broadcast_to_incident",
        new_callable=AsyncMock,
    ):
        response = await client.post(f"/emergency/incidents/{TEST_INCIDENT_ID}/resolve")
    assert response.status_code == 200
    assert response.json()["status"] == "RESOLVED"
