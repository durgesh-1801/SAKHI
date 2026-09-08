"""
ARIA / SAKHI — WebSocket Handlers
====================================
BE3 OWNS THIS FILE.

Handles the full WebSocket connection lifecycle for an emergency incident:
  1. Token validation (auth)
  2. Incident authorization (owner or trusted contact)
  3. Message loop (location updates from mobile app, ping/pong)
  4. Clean disconnect on error or close

WebSocket protocol:
  Connect:  wss://host/ws/emergency/{incident_id}?token=<JWT>
  Reject:   HTTP 4001/4003 close code with error JSON before disconnect

  Client → Server:
    { "event": "location_update", "latitude": ..., "longitude": ..., "accuracy": ... }
    { "event": "ping" }

  Server → Client:
    { "event": "location_update", ... }
    { "event": "incident_update", ... }
    { "event": "verification_request", ... }
    { "event": "contact_notified", ... }
    { "event": "incident_resolved", ... }
    { "event": "pong" }
    { "event": "error", "code": ..., "message": ... }
"""

import logging
import uuid
from datetime import UTC, datetime
from typing import Any

from fastapi import WebSocket, WebSocketDisconnect
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.emergency import EmergencyIncident
from app.schemas.user import UserRead
from app.websocket.manager import ws_manager

logger = logging.getLogger(__name__)

# WebSocket close codes
WS_CLOSE_UNAUTHORIZED = 4001
WS_CLOSE_FORBIDDEN = 4003
WS_CLOSE_NOT_FOUND = 4004
WS_CLOSE_INCIDENT_INACTIVE = 4010


async def handle_websocket_connection(
    websocket: WebSocket,
    incident_id: str,
    token: str,
    db: AsyncSession,
) -> None:
    """
    Full WebSocket connection handler.

    Step 1: Authenticate the token.
    Step 2: Load the incident.
    Step 3: Authorize the connection (owner or trusted contact).
    Step 4: Accept and enter message loop.
    Step 5: Handle disconnect.
    """
    # ── Step 1: Authenticate ──────────────────────────────────────────────────
    current_user = await _authenticate_ws_token(token, websocket)
    if current_user is None:
        return  # Already closed with 4001

    # ── Step 2: Load incident ─────────────────────────────────────────────────
    try:
        incident_uuid = uuid.UUID(incident_id)
    except ValueError:
        await websocket.close(code=WS_CLOSE_NOT_FOUND, reason="Invalid incident ID format.")
        return

    result = await db.execute(
        select(EmergencyIncident).where(EmergencyIncident.id == incident_uuid)
    )
    incident = result.scalar_one_or_none()

    if incident is None:
        await websocket.close(code=WS_CLOSE_NOT_FOUND, reason="Incident not found.")
        return

    # ── Step 3: Authorize ─────────────────────────────────────────────────────
    is_owner = incident.user_id == current_user.id
    is_guardian = False

    if not is_owner:
        from app.services.contact_service import is_trusted_contact

        is_guardian = await is_trusted_contact(
            guardian_user_id=current_user.id,
            incident_user_id=incident.user_id,
            db=db,
        )

    if not (is_owner or is_guardian):
        await websocket.close(
            code=WS_CLOSE_FORBIDDEN,
            reason="You are not authorized to access this incident.",
        )
        return

    # ── Step 4: Accept + message loop ─────────────────────────────────────────
    await ws_manager.connect(incident_id, websocket)

    # Send welcome snapshot
    await ws_manager.send_to_connection(
        websocket,
        {
            "event": "connected",
            "incident_id": incident_id,
            "status": incident.status,
            "role": "owner" if is_owner else "guardian",
            "timestamp": datetime.now(UTC).isoformat(),
        },
    )

    try:
        while True:
            data = await websocket.receive_json()
            await _handle_client_message(
                data=data,
                incident=incident,
                is_owner=is_owner,
                websocket=websocket,
                db=db,
            )
    except WebSocketDisconnect:
        logger.info(
            "WebSocket disconnected for incident %s (user %s).",
            incident_id,
            current_user.id,
        )
    except Exception as exc:  # noqa: BLE001
        logger.error("WebSocket error for incident %s: %s", incident_id, exc)
    finally:
        await ws_manager.disconnect(incident_id, websocket)


async def _authenticate_ws_token(
    token: str,
    websocket: WebSocket,
) -> UserRead | None:
    """
    Validate the Bearer token before accepting the WebSocket.

    BE1 INTEGRATION: This calls get_current_user which is BE1's auth stub.
    Once BE1 implements JWT validation, this works automatically.

    Returns the UserRead if valid, closes with 4001 and returns None if invalid.
    """
    try:
        # Simulate the OAuth2 dependency manually for WebSocket context
        from app.auth.dependencies import get_current_user

        # get_current_user expects an OAuth2 token string — call it directly
        # We use a minimal FastAPI dependency workaround for WebSocket
        current_user = await get_current_user(token=token)
        return current_user
    except Exception as exc:  # noqa: BLE001
        logger.warning("WebSocket auth failed: %s", exc)
        await websocket.close(
            code=WS_CLOSE_UNAUTHORIZED,
            reason="Authentication failed. Provide a valid token query parameter.",
        )
        return None


async def _handle_client_message(
    data: dict[str, Any],
    incident: EmergencyIncident,
    is_owner: bool,
    websocket: WebSocket,
    db: AsyncSession,
) -> None:
    """Route an incoming client message to the appropriate handler."""
    event = data.get("event")

    if event == "ping":
        await ws_manager.send_to_connection(websocket, {"event": "pong"})
        return

    if event == "location_update":
        if not is_owner:
            # Guardians cannot push location — only the user (incident owner) can
            await ws_manager.send_to_connection(
                websocket,
                {
                    "event": "error",
                    "code": "FORBIDDEN",
                    "message": "Only the incident owner can send location updates.",
                },
            )
            return

        await _handle_location_update(data=data, incident=incident, db=db)
        return

    # Unknown event
    await ws_manager.send_to_connection(
        websocket,
        {"event": "error", "code": "UNKNOWN_EVENT", "message": f"Unknown event: {event}"},
    )


async def _handle_location_update(
    data: dict[str, Any],
    incident: EmergencyIncident,
    db: AsyncSession,
) -> None:
    """
    Process a location update from the mobile app (incident owner).

    Updates the incident's latest location and broadcasts to all
    connections in the room (including guardians).
    """
    try:
        latitude = float(data["latitude"])
        longitude = float(data["longitude"])
        accuracy = float(data["accuracy"]) if data.get("accuracy") is not None else None

        # Validate ranges
        if not (-90 <= latitude <= 90) or not (-180 <= longitude <= 180):
            return

    except (KeyError, ValueError, TypeError):
        return

    if not incident.is_active:
        return  # Don't update location for resolved/cancelled incidents

    from app.services.location_service import process_location_update

    await process_location_update(
        incident=incident,
        latitude=latitude,
        longitude=longitude,
        accuracy=accuracy,
        db=db,
    )
    await db.commit()
