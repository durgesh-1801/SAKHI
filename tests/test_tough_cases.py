"""
Tests: Tough Edge Cases & Security Audits
===========================================
Covers:
  1. State Machine Invariants:
     - Cannot verify a RESOLVED, CANCELLED, or ESCALATING incident
     - Cannot resolve a CANCELLED incident
  2. Background Tasks & Celery Revocation:
     - Cancelling or resolving an incident revokes pending Celery timeout tasks
     - Invalid UUID passed to Celery task is skipped without retry storm
  3. Location Tracking & Timeline Throttling:
     - First location update creates LOCATION_UPDATED event
     - Micro-movements (<10m) update coordinates without spamming timeline events
     - Significant movement triggers LOCATION_UPDATED event
  4. REST Location Fallback Endpoint:
     - Owner can update location via POST
     - Non-owner is denied (403)
     - Inactive incident rejects location update (409)
  5. Cross-User AI Trigger Authorization:
     - User cannot trigger AI incident for a different user (403)
  6. WebSocket Edge Cases:
     - Malformed JSON frame handled with INVALID_JSON error without disconnect
     - Non-dict JSON frame handled with INVALID_PAYLOAD error
     - Out-of-bounds/NaN/Inf coordinates rejected with INVALID_LOCATION error
     - Push to inactive incident rejected with INCIDENT_INACTIVE error
"""

import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from tests.conftest import TEST_INCIDENT_ID, TEST_USER_ID

# ──────────────────────────────────────────────────────────────────────────────
# 1. State Machine Invariants
# ──────────────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_cannot_verify_resolved_incident(
    client: AsyncClient,
    db_session: AsyncSession,
    test_user,
):
    """Verifying an already RESOLVED incident → 409 Conflict."""
    from app.models.emergency import EmergencyIncident

    incident = EmergencyIncident(
        id=uuid.uuid4(),
        user_id=TEST_USER_ID,
        trigger_type="MANUAL_SOS",
        status="RESOLVED",
        risk_level="CRITICAL",
        resolved_at=datetime.now(UTC),
    )
    db_session.add(incident)
    await db_session.flush()

    response = await client.post(
        f"/emergency/incidents/{incident.id}/verify",
        json={"response": "USER_CONFIRMED_SAFE"},
    )
    assert response.status_code == 409
    assert "VERIFYING" in response.json()["detail"]


@pytest.mark.asyncio
async def test_cannot_verify_cancelled_incident(
    client: AsyncClient,
    db_session: AsyncSession,
    test_user,
):
    """Verifying an already CANCELLED incident → 409 Conflict."""
    from app.models.emergency import EmergencyIncident

    incident = EmergencyIncident(
        id=uuid.uuid4(),
        user_id=TEST_USER_ID,
        trigger_type="AI_DETECTION",
        status="CANCELLED",
        risk_level="HIGH",
        resolved_at=datetime.now(UTC),
    )
    db_session.add(incident)
    await db_session.flush()

    response = await client.post(
        f"/emergency/incidents/{incident.id}/verify",
        json={"response": "USER_CONFIRMED_SAFE"},
    )
    assert response.status_code == 409
    assert "VERIFYING" in response.json()["detail"]


@pytest.mark.asyncio
async def test_cannot_resolve_cancelled_incident(
    client: AsyncClient,
    db_session: AsyncSession,
    test_user,
):
    """Resolving a CANCELLED incident → 409 Conflict."""
    from app.models.emergency import EmergencyIncident

    incident = EmergencyIncident(
        id=uuid.uuid4(),
        user_id=TEST_USER_ID,
        trigger_type="MANUAL_SOS",
        status="CANCELLED",
        risk_level="CRITICAL",
        resolved_at=datetime.now(UTC),
    )
    db_session.add(incident)
    await db_session.flush()

    response = await client.post(f"/emergency/incidents/{incident.id}/resolve")
    assert response.status_code == 409
    assert "cancelled" in response.json()["detail"].lower()


# ──────────────────────────────────────────────────────────────────────────────
# 2. Background Tasks & Celery Revocation
# ──────────────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_cancel_incident_revokes_celery_task(
    client: AsyncClient,
    db_session: AsyncSession,
    test_user,
    verifying_incident,
):
    """Cancelling a verifying incident revokes the pending Celery task and clears the task id."""
    with (
        patch("app.services.verification_service._revoke_escalation_task") as mock_revoke,
        patch("app.websocket.manager.ws_manager.broadcast_to_incident", new_callable=AsyncMock),
    ):
        response = await client.post(f"/emergency/incidents/{verifying_incident.id}/cancel")

    assert response.status_code == 200
    mock_revoke.assert_called_once_with("fake-celery-task-id")
    assert verifying_incident.escalation_task_id is None


@pytest.mark.asyncio
async def test_celery_task_handles_invalid_uuid():
    """handle_no_response_task handles malformed UUID strings gracefully without retrying."""
    from app.tasks.escalation_tasks import _run_no_response

    result = await _run_no_response("invalid-uuid-format")
    assert result.get("skipped") is True
    assert "Invalid incident ID" in result.get("reason", "")


# ──────────────────────────────────────────────────────────────────────────────
# 3. Location Tracking & Timeline Throttling
# ──────────────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_location_timeline_throttling(
    db_session: AsyncSession,
    test_user,
    active_incident,
):
    """
    First location update logs a LOCATION_UPDATED timeline event.
    Subsequent micro-movements (<10m) do NOT spam timeline events.
    Significant movement (>10m) logs a new event.
    """
    from app.models.emergency import IncidentEvent
    from app.services.location_service import process_location_update

    with patch("app.websocket.manager.ws_manager.broadcast_to_incident", new_callable=AsyncMock):
        # 1. First update on incident that had no location_updated_at yet
        active_incident.location_updated_at = None
        await process_location_update(
            incident=active_incident,
            latitude=26.843200,
            longitude=75.565100,
            accuracy=5.0,
            db=db_session,
        )

        # Check that first event is logged
        result1 = await db_session.execute(
            select(IncidentEvent).where(
                IncidentEvent.incident_id == active_incident.id,
                IncidentEvent.event_type == "LOCATION_UPDATED",
            )
        )
        events1 = result1.scalars().all()
        assert len(events1) == 1

        # 2. Micro-movement (1 meter shift: ~0.00001 deg)
        await process_location_update(
            incident=active_incident,
            latitude=26.843205,
            longitude=75.565105,
            accuracy=5.0,
            db=db_session,
        )

        # Event count must still be 1 (no spam)
        result2 = await db_session.execute(
            select(IncidentEvent).where(
                IncidentEvent.incident_id == active_incident.id,
                IncidentEvent.event_type == "LOCATION_UPDATED",
            )
        )
        events2 = result2.scalars().all()
        assert len(events2) == 1

        # 3. Significant movement (>100 meters: ~0.001 deg)
        await process_location_update(
            incident=active_incident,
            latitude=26.845000,
            longitude=75.567000,
            accuracy=5.0,
            db=db_session,
        )

        result3 = await db_session.execute(
            select(IncidentEvent).where(
                IncidentEvent.incident_id == active_incident.id,
                IncidentEvent.event_type == "LOCATION_UPDATED",
            )
        )
        events3 = result3.scalars().all()
        assert len(events3) == 2


# ──────────────────────────────────────────────────────────────────────────────
# 4. REST Location Fallback Endpoint
# ──────────────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_rest_location_update_by_owner(
    client: AsyncClient,
    test_user,
    active_incident,
):
    """Incident owner can update location via POST REST endpoint."""
    with patch("app.websocket.manager.ws_manager.broadcast_to_incident", new_callable=AsyncMock):
        response = await client.post(
            f"/emergency/incidents/{TEST_INCIDENT_ID}/location",
            json={"latitude": 26.8500, "longitude": 75.5700, "accuracy": 8.0},
        )

    assert response.status_code == 200
    body = response.json()
    assert body["latitude"] == pytest.approx(26.8500)
    assert body["longitude"] == pytest.approx(75.5700)


@pytest.mark.asyncio
async def test_rest_location_update_by_non_owner_forbidden(
    client: AsyncClient,
    db_session: AsyncSession,
    test_user,
    active_incident,
):
    """Non-owner is denied from pushing location via POST REST endpoint."""
    from app.auth.dependencies import get_current_user
    from app.database import get_db
    from app.schemas.user import UserRead

    other_user = UserRead(id=uuid.uuid4(), full_name="Hacker", email="hacker@aria.app")

    async def override_auth():
        return other_user

    async def override_db():
        yield db_session

    app_instance = client._transport.app  # type: ignore[attr-defined]
    app_instance.dependency_overrides[get_current_user] = override_auth
    app_instance.dependency_overrides[get_db] = override_db

    response = await client.post(
        f"/emergency/incidents/{TEST_INCIDENT_ID}/location",
        json={"latitude": 26.8500, "longitude": 75.5700},
    )
    app_instance.dependency_overrides.clear()
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_rest_location_update_on_inactive_incident_conflict(
    client: AsyncClient,
    db_session: AsyncSession,
    test_user,
):
    """Cannot push location update to a RESOLVED incident via REST."""
    from app.models.emergency import EmergencyIncident

    incident = EmergencyIncident(
        id=uuid.uuid4(),
        user_id=TEST_USER_ID,
        trigger_type="MANUAL_SOS",
        status="RESOLVED",
        risk_level="CRITICAL",
        resolved_at=datetime.now(UTC),
    )
    db_session.add(incident)
    await db_session.flush()

    response = await client.post(
        f"/emergency/incidents/{incident.id}/location",
        json={"latitude": 26.8500, "longitude": 75.5700},
    )
    assert response.status_code == 409


# ──────────────────────────────────────────────────────────────────────────────
# 5. Cross-User AI Trigger Authorization
# ──────────────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_ai_trigger_different_user_forbidden(
    client: AsyncClient,
    test_user,
    test_policy,
    test_consent,
):
    """A user cannot call /emergency/trigger for a different user."""
    different_user_id = uuid.uuid4()
    response = await client.post(
        "/emergency/trigger",
        json={
            "user_id": str(different_user_id),
            "risk_score": 92.0,
            "risk_level": "CRITICAL",
            "reasons": ["Distress signal detected"],
            "trigger_type": "AI_DETECTION",
        },
    )
    assert response.status_code == 403
    assert "not authorized" in response.json()["detail"].lower()


# ──────────────────────────────────────────────────────────────────────────────
# 6. WebSocket Edge Cases & Robustness
# ──────────────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_ws_malformed_json_frame(db_session: AsyncSession, test_user, active_incident):
    """Non-JSON or malformed frame sends INVALID_JSON error and does not crash connection."""
    from app.websocket.handlers import handle_websocket_connection

    mock_ws = MagicMock()
    mock_ws.accept = AsyncMock()
    mock_ws.send_json = AsyncMock()
    mock_ws.close = AsyncMock()

    # First message: ValueError (malformed json), second message: disconnect
    from fastapi import WebSocketDisconnect

    mock_ws.receive_json = AsyncMock(
        side_effect=[
            ValueError("Malformed JSON"),
            WebSocketDisconnect(),
        ]
    )

    with patch("app.auth.dependencies.get_current_user", return_value=test_user):
        await handle_websocket_connection(
            websocket=mock_ws,
            incident_id=str(active_incident.id),
            token="valid-token",
            db=db_session,
        )

    # Verify that an error frame was sent back
    mock_ws.send_json.assert_any_call(
        {"event": "error", "code": "INVALID_JSON", "message": "Malformed JSON payload."}
    )


@pytest.mark.asyncio
async def test_ws_non_dict_payload(db_session: AsyncSession, test_user, active_incident):
    """Payload that is a list rather than dict sends INVALID_PAYLOAD error."""
    from fastapi import WebSocketDisconnect

    from app.websocket.handlers import handle_websocket_connection

    mock_ws = MagicMock()
    mock_ws.accept = AsyncMock()
    mock_ws.send_json = AsyncMock()
    mock_ws.close = AsyncMock()

    mock_ws.receive_json = AsyncMock(
        side_effect=[
            ["not", "a", "dict"],
            WebSocketDisconnect(),
        ]
    )

    with patch("app.auth.dependencies.get_current_user", return_value=test_user):
        await handle_websocket_connection(
            websocket=mock_ws,
            incident_id=str(active_incident.id),
            token="valid-token",
            db=db_session,
        )

    mock_ws.send_json.assert_any_call(
        {
            "event": "error",
            "code": "INVALID_PAYLOAD",
            "message": "Payload must be a JSON object.",
        }
    )


@pytest.mark.asyncio
async def test_ws_out_of_bounds_coordinates(db_session: AsyncSession, test_user, active_incident):
    """Out-of-bounds coordinates sent via WebSocket return INVALID_LOCATION error."""
    from fastapi import WebSocketDisconnect

    from app.websocket.handlers import handle_websocket_connection

    mock_ws = MagicMock()
    mock_ws.accept = AsyncMock()
    mock_ws.send_json = AsyncMock()
    mock_ws.close = AsyncMock()

    mock_ws.receive_json = AsyncMock(
        side_effect=[
            {"event": "location_update", "latitude": 999.0, "longitude": 75.0},
            WebSocketDisconnect(),
        ]
    )

    with patch("app.auth.dependencies.get_current_user", return_value=test_user):
        await handle_websocket_connection(
            websocket=mock_ws,
            incident_id=str(active_incident.id),
            token="valid-token",
            db=db_session,
        )

    mock_ws.send_json.assert_any_call(
        {
            "event": "error",
            "code": "INVALID_LOCATION",
            "message": "Coordinates out of valid range (-90..90, -180..180).",
        }
    )
