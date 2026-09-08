"""
Tests: Location Service & Guardian Location Endpoint
======================================================
Covers:
  - Location update persists to DB
  - Location update broadcasts via WebSocket
  - Multiple location updates accumulate in history
  - GET /location returns latest coordinates
  - Resolved incident with no location → 404 on location endpoint
"""

import uuid
from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from tests.conftest import TEST_INCIDENT_ID


@pytest.mark.asyncio
async def test_location_update_persists_to_db(
    db_session: AsyncSession,
    test_user,
    active_incident,
):
    """process_location_update stores a row in incident_location_updates."""
    from app.models.emergency import IncidentLocationUpdate
    from app.services.location_service import process_location_update

    with patch(
        "app.websocket.manager.ws_manager.broadcast_to_incident",
        new_callable=AsyncMock,
    ):
        await process_location_update(
            incident=active_incident,
            latitude=26.8432,
            longitude=75.5651,
            accuracy=5.0,
            db=db_session,
        )

    result = await db_session.execute(
        select(IncidentLocationUpdate).where(IncidentLocationUpdate.incident_id == TEST_INCIDENT_ID)
    )
    rows = result.scalars().all()
    assert len(rows) >= 1
    assert rows[-1].latitude == pytest.approx(26.8432)
    assert rows[-1].longitude == pytest.approx(75.5651)


@pytest.mark.asyncio
async def test_location_update_updates_incident_latest(
    db_session: AsyncSession,
    test_user,
    active_incident,
):
    """After update, incident.latitude/longitude reflect the new coordinates."""
    from app.services.location_service import process_location_update

    with patch(
        "app.websocket.manager.ws_manager.broadcast_to_incident",
        new_callable=AsyncMock,
    ):
        await process_location_update(
            incident=active_incident,
            latitude=28.6139,
            longitude=77.2090,
            accuracy=10.0,
            db=db_session,
        )

    assert active_incident.latitude == pytest.approx(28.6139)
    assert active_incident.longitude == pytest.approx(77.2090)
    assert active_incident.location_accuracy == pytest.approx(10.0)


@pytest.mark.asyncio
async def test_location_update_broadcasts_ws(
    db_session: AsyncSession,
    test_user,
    active_incident,
):
    """Location update triggers a WebSocket broadcast to the incident room."""
    from app.services.location_service import process_location_update

    with patch(
        "app.websocket.manager.ws_manager.broadcast_to_incident",
        new_callable=AsyncMock,
    ) as mock_broadcast:
        await process_location_update(
            incident=active_incident,
            latitude=26.8432,
            longitude=75.5651,
            accuracy=5.0,
            db=db_session,
        )

    mock_broadcast.assert_called_once()
    call_args = mock_broadcast.call_args
    event_data = call_args[0][1]
    assert event_data["event"] == "location_update"
    assert event_data["latitude"] == pytest.approx(26.8432)
    assert event_data["incident_id"] == str(TEST_INCIDENT_ID)


@pytest.mark.asyncio
async def test_multiple_location_updates_accumulate(
    db_session: AsyncSession,
    test_user,
    active_incident,
):
    """Multiple location updates all persist as separate history rows."""
    from app.models.emergency import IncidentLocationUpdate
    from app.services.location_service import process_location_update

    coords = [
        (26.8432, 75.5651),
        (26.8435, 75.5655),
        (26.8440, 75.5660),
    ]

    with patch(
        "app.websocket.manager.ws_manager.broadcast_to_incident",
        new_callable=AsyncMock,
    ):
        for lat, lon in coords:
            await process_location_update(
                incident=active_incident,
                latitude=lat,
                longitude=lon,
                accuracy=5.0,
                db=db_session,
            )

    result = await db_session.execute(
        select(IncidentLocationUpdate).where(IncidentLocationUpdate.incident_id == TEST_INCIDENT_ID)
    )
    rows = result.scalars().all()
    assert len(rows) == 3


@pytest.mark.asyncio
async def test_get_location_endpoint_returns_latest(
    client: AsyncClient,
    test_user,
    active_incident,
):
    """GET /emergency/incidents/{id}/location returns latest coordinates."""
    response = await client.get(f"/emergency/incidents/{TEST_INCIDENT_ID}/location")
    assert response.status_code == 200
    body = response.json()
    assert body["latitude"] == pytest.approx(26.8432)
    assert body["longitude"] == pytest.approx(75.5651)
    assert body["status"] == "ACTIVE"


@pytest.mark.asyncio
async def test_location_not_found_for_unknown_incident(
    client: AsyncClient,
    test_user,
):
    """GET /location for a nonexistent incident → 404."""
    response = await client.get(f"/emergency/incidents/{uuid.uuid4()}/location")
    assert response.status_code == 404
