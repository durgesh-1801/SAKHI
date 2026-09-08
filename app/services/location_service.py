"""
ARIA / SAKHI — Location Service
==================================
BE3 OWNS THIS FILE.

Processes location updates during an active emergency:
  - Persists to IncidentLocationUpdate (history)
  - Updates EmergencyIncident latest location (fast read)
  - Logs timeline event
  - Broadcasts to authorized guardians via WebSocket
"""

import logging
from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.emergency import EmergencyIncident
from app.services.emergency_service import log_event, update_incident_location
from app.websocket.manager import ws_manager

logger = logging.getLogger(__name__)


async def process_location_update(
    incident: EmergencyIncident,
    latitude: float,
    longitude: float,
    accuracy: float | None,
    db: AsyncSession,
) -> None:
    """
    Handle a single location update from the mobile app during an active incident.

    1. Persist to location history.
    2. Update incident's latest location.
    3. Log a LOCATION_UPDATED timeline event.
    4. Broadcast to all WebSocket subscribers (guardians + owner).
    """
    # 1 & 2: Persist history + update latest location on incident
    await update_incident_location(
        incident=incident,
        latitude=latitude,
        longitude=longitude,
        accuracy=accuracy,
        db=db,
    )

    # 3: Timeline event (not every update — only if significant change or first update)
    # To avoid flooding the timeline, log every 10th update or first update.
    # We use the existing location history count as a proxy — simple and effective.
    should_log_event = (
        incident.location_updated_at is None  # first update
        or _is_significant_change(incident.latitude, incident.longitude, latitude, longitude)
    )

    if should_log_event:
        await log_event(
            db,
            incident.id,
            "LOCATION_UPDATED",
            f"Location updated: ({latitude:.6f}, {longitude:.6f})",
            {
                "latitude": latitude,
                "longitude": longitude,
                "accuracy": accuracy,
            },
        )

    # 4: Broadcast to WebSocket room
    await ws_manager.broadcast_to_incident(
        str(incident.id),
        {
            "event": "location_update",
            "incident_id": str(incident.id),
            "latitude": latitude,
            "longitude": longitude,
            "accuracy": accuracy,
            "timestamp": datetime.now(UTC).isoformat(),
        },
    )
    logger.debug(
        "Location broadcast for incident %s: (%.6f, %.6f)",
        incident.id,
        latitude,
        longitude,
    )


def _is_significant_change(
    old_lat: float | None,
    old_lon: float | None,
    new_lat: float,
    new_lon: float,
    threshold_deg: float = 0.0001,  # ~10 metres
) -> bool:
    """
    Returns True if the location change is significant enough to log a timeline event.
    Prevents the timeline from being flooded with near-identical location entries.
    """
    if old_lat is None or old_lon is None:
        return True
    return abs(new_lat - old_lat) > threshold_deg or abs(new_lon - old_lon) > threshold_deg
