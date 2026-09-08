"""
Tests: WebSocket Connection Manager
=====================================
Covers:
  - connect adds connection to room
  - disconnect removes connection from room
  - broadcast_to_incident sends to all room members
  - broadcast skips dead connections and removes them
  - Empty room broadcast is a no-op (no error)
  - get_connection_count and get_active_incident_ids
"""

from unittest.mock import AsyncMock, MagicMock

import pytest

from app.websocket.manager import ConnectionManager


@pytest.fixture
def manager() -> ConnectionManager:
    """Fresh ConnectionManager per test."""
    return ConnectionManager()


@pytest.fixture
def fake_websocket() -> MagicMock:
    """Mock WebSocket that accepts and sends JSON."""
    ws = MagicMock()
    ws.accept = AsyncMock()
    ws.send_json = AsyncMock()
    ws.close = AsyncMock()
    return ws


INCIDENT_A = "incident-aaa"
INCIDENT_B = "incident-bbb"


@pytest.mark.asyncio
async def test_connect_adds_to_room(manager: ConnectionManager, fake_websocket):
    """connect() accepts the socket and adds it to the room."""
    await manager.connect(INCIDENT_A, fake_websocket)
    fake_websocket.accept.assert_called_once()
    assert manager.get_connection_count(INCIDENT_A) == 1


@pytest.mark.asyncio
async def test_disconnect_removes_from_room(manager: ConnectionManager, fake_websocket):
    """disconnect() removes the socket and cleans up empty rooms."""
    await manager.connect(INCIDENT_A, fake_websocket)
    await manager.disconnect(INCIDENT_A, fake_websocket)
    assert manager.get_connection_count(INCIDENT_A) == 0
    assert INCIDENT_A not in manager.get_active_incident_ids()


@pytest.mark.asyncio
async def test_broadcast_sends_to_all_connections(manager: ConnectionManager):
    """broadcast_to_incident sends the message to every connected socket."""
    ws1, ws2 = MagicMock(), MagicMock()
    ws1.accept = AsyncMock()
    ws2.accept = AsyncMock()
    ws1.send_json = AsyncMock()
    ws2.send_json = AsyncMock()

    await manager.connect(INCIDENT_A, ws1)
    await manager.connect(INCIDENT_A, ws2)

    payload = {"event": "location_update", "incident_id": INCIDENT_A}
    await manager.broadcast_to_incident(INCIDENT_A, payload)

    ws1.send_json.assert_called_once_with(payload)
    ws2.send_json.assert_called_once_with(payload)


@pytest.mark.asyncio
async def test_broadcast_removes_dead_connections(manager: ConnectionManager):
    """Dead connections (send_json raises) are silently removed."""
    ws_live = MagicMock()
    ws_dead = MagicMock()
    ws_live.accept = AsyncMock()
    ws_dead.accept = AsyncMock()
    ws_live.send_json = AsyncMock()
    ws_dead.send_json = AsyncMock(side_effect=RuntimeError("connection closed"))

    await manager.connect(INCIDENT_A, ws_live)
    await manager.connect(INCIDENT_A, ws_dead)

    assert manager.get_connection_count(INCIDENT_A) == 2

    await manager.broadcast_to_incident(INCIDENT_A, {"event": "test"})

    # Live socket received the message; dead socket was removed
    ws_live.send_json.assert_called_once()
    assert manager.get_connection_count(INCIDENT_A) == 1


@pytest.mark.asyncio
async def test_broadcast_empty_room_is_noop(manager: ConnectionManager):
    """Broadcasting to a room with no connections does not raise."""
    # Should not raise
    await manager.broadcast_to_incident("nonexistent-incident", {"event": "test"})


@pytest.mark.asyncio
async def test_multiple_rooms_are_isolated(manager: ConnectionManager):
    """Connections in different rooms do not receive each other's broadcasts."""
    ws_a = MagicMock()
    ws_b = MagicMock()
    ws_a.accept = AsyncMock()
    ws_b.accept = AsyncMock()
    ws_a.send_json = AsyncMock()
    ws_b.send_json = AsyncMock()

    await manager.connect(INCIDENT_A, ws_a)
    await manager.connect(INCIDENT_B, ws_b)

    await manager.broadcast_to_incident(INCIDENT_A, {"event": "for_a"})

    ws_a.send_json.assert_called_once_with({"event": "for_a"})
    ws_b.send_json.assert_not_called()


@pytest.mark.asyncio
async def test_get_active_incident_ids(manager: ConnectionManager, fake_websocket):
    """get_active_incident_ids returns IDs of rooms with connections."""
    ws2 = MagicMock()
    ws2.accept = AsyncMock()
    ws2.send_json = AsyncMock()

    await manager.connect(INCIDENT_A, fake_websocket)
    await manager.connect(INCIDENT_B, ws2)

    active = manager.get_active_incident_ids()
    assert INCIDENT_A in active
    assert INCIDENT_B in active


@pytest.mark.asyncio
async def test_send_to_connection_returns_false_on_error(manager: ConnectionManager):
    """send_to_connection returns False if the socket is dead."""
    ws = MagicMock()
    ws.send_json = AsyncMock(side_effect=RuntimeError("closed"))

    result = await manager.send_to_connection(ws, {"event": "test"})
    assert result is False
