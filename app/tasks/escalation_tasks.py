"""
ARIA / SAKHI — Escalation Tasks (Celery)
==========================================
BE3 OWNS THIS FILE.

Background tasks for the escalation engine:
  - handle_no_response_task: fires after the verification timeout
    if the user has not responded to the "Are you safe?" prompt.
"""

import asyncio
import uuid
from typing import Any

from app.tasks.celery_app import celery_app


@celery_app.task(  # type: ignore[misc]
    name="aria.emergency.handle_no_response",
    bind=True,
    max_retries=3,
    default_retry_delay=5,
    acks_late=True,
)
def handle_no_response_task(self: Any, incident_id: str) -> dict[str, Any]:
    """
    Fired by the verification timeout.

    Runs the no-response escalation path:
      1. Load the incident — verify it is still in VERIFYING status
         (if the user already responded, do nothing).
      2. Log NO_RESPONSE event.
      3. Execute the escalation policy.
      4. Notify trusted contacts.
      5. Start location sharing if consent is given.

    This task runs in a Celery worker (separate process).
    It creates its own async event loop to call async services.
    """
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        result = loop.run_until_complete(_run_no_response(incident_id))
        return result
    except Exception as exc:  # noqa: BLE001
        raise self.retry(exc=exc) from exc
    finally:
        loop.close()


async def _run_no_response(incident_id: str) -> dict[str, Any]:
    """Async implementation called from the sync Celery task."""
    from sqlalchemy import select

    from app.database import AsyncSessionLocal
    from app.models.emergency import EmergencyIncident
    from app.services.escalation_service import execute_no_response_escalation

    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(EmergencyIncident).where(EmergencyIncident.id == uuid.UUID(incident_id))
        )
        incident = result.scalar_one_or_none()

        if incident is None:
            return {"skipped": True, "reason": "Incident not found"}

        if incident.status != "VERIFYING":
            # User already responded — nothing to do
            return {
                "skipped": True,
                "reason": f"Incident already in status {incident.status}",
            }

        await execute_no_response_escalation(incident=incident, db=db)
        await db.commit()

        return {"incident_id": incident_id, "escalated": True}
