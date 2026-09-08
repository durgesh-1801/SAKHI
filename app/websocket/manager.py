"""
ARIA / SAKHI — WebSocket Connection Manager
=============================================
BE3 OWNS THIS FILE.

Manages all active WebSocket connections across emergency incidents.

Architecture:
  - Each incident has a "room" identified by incident_id (str/UUID).
  - Both the incident owner (user) and authorized guardians connect to the same room.
  - Location updates from the mobile app (user) are broadcast to all room members.
  - Unauthorized connections are rejected before being accepted.

Thread safety:
  - FastAPI runs in a single async event loop per worker.
  - This manager uses asyncio.Lock for safe concurrent access.
  - For multi-worker deployments, Redis pub/sub is needed (see TODO below).

TODO: For horizontal scaling, replace the in-process dict with Redis pub/sub
      so connections on different workers receive broadcasts.
"""

import asyncio
import logging
from collections import defaultdict
from typing import Any

from fastapi import WebSocket

logger = logging.getLogger(__name__)


class ConnectionManager:
    """
    In-process WebSocket connection manager.

    Rooms are keyed by incident_id (str).
    Each room is a set of active WebSocket connections.
    """

    def __init__(self) -> None:
        # incident_id → set of connected WebSockets
        self._rooms: defaultdict[str, set[WebSocket]] = defaultdict(set)
        self._lock = asyncio.Lock()

    async def connect(self, incident_id: str, websocket: WebSocket) -> None:
        """Accept and register a WebSocket connection."""
        await websocket.accept()
        async with self._lock:
            self._rooms[incident_id].add(websocket)
        logger.info(
            "WebSocket connected to incident %s. Total: %d",
            incident_id,
            len(self._rooms[incident_id]),
        )

    async def disconnect(self, incident_id: str, websocket: WebSocket) -> None:
        """Remove a WebSocket connection from its room."""
        async with self._lock:
            self._rooms[incident_id].discard(websocket)
            if not self._rooms[incident_id]:
                del self._rooms[incident_id]
        logger.info("WebSocket disconnected from incident %s.", incident_id)

    async def broadcast_to_incident(
        self,
        incident_id: str,
        message: dict[str, Any],
    ) -> None:
        """
        Broadcast a JSON message to all connections in an incident room.
        Dead connections are silently removed.
        """
        async with self._lock:
            connections = set(self._rooms.get(incident_id, set()))

        if not connections:
            return

        dead: set[WebSocket] = set()
        for websocket in connections:
            try:
                await websocket.send_json(message)
            except Exception:  # noqa: BLE001
                dead.add(websocket)

        # Clean up dead connections
        if dead:
            async with self._lock:
                self._rooms[incident_id] -= dead
                if not self._rooms[incident_id]:
                    self._rooms.pop(incident_id, None)

    async def send_to_connection(
        self,
        websocket: WebSocket,
        message: dict[str, Any],
    ) -> bool:
        """Send a message to a single connection. Returns False if send fails."""
        try:
            await websocket.send_json(message)
            return True
        except Exception:  # noqa: BLE001
            return False

    def get_connection_count(self, incident_id: str) -> int:
        """Return number of active connections for an incident (for monitoring)."""
        return len(self._rooms.get(incident_id, set()))

    def get_active_incident_ids(self) -> list[str]:
        """Return list of incident IDs with active connections."""
        return list(self._rooms.keys())


# ── Singleton — imported by all modules that need to broadcast ─────────────────
ws_manager = ConnectionManager()
