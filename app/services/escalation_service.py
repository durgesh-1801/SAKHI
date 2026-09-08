"""
ARIA / SAKHI — Escalation Service
====================================
BE3 OWNS THIS FILE.

Responsible for EXECUTING the user's emergency policy.
Never creates or modifies the policy — that belongs to BE2.

Entry points:
  start_escalation          — called immediately after incident creation
  execute_escalation        — policy-driven escalation (contacts + location)
  execute_no_response_escalation  — called from Celery on timeout
"""

from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.contact import TrustedContact
from app.models.emergency import EmergencyIncident
from app.models.policy import EmergencyPolicy
from app.schemas.user import UserRead
from app.services import consent_service, contact_service
from app.services.emergency_service import log_event, update_incident_status

# ──────────────────────────────────────────────────────────────────────────────
# PUBLIC ENTRY POINT — called right after incident creation
# ──────────────────────────────────────────────────────────────────────────────


async def start_escalation(
    incident: EmergencyIncident,
    user: UserRead,
    policy: EmergencyPolicy,
    db: AsyncSession,
) -> None:
    """
    Start the escalation pipeline for a newly created incident.

    For MANUAL_SOS: notifies contacts immediately (no verification window).
    For AI_DETECTION / others: sends verification first, then escalates on timeout.

    The trigger determines whether we skip straight to escalation or verify first.
    """
    if incident.trigger_type == "MANUAL_SOS":
        # Manual SOS — user explicitly triggered. Skip verification, escalate immediately.
        await execute_escalation(
            incident=incident,
            user=user,
            policy=policy,
            db=db,
        )
    else:
        # AI/detection triggers — verify first (consent-first design)
        from app.services.verification_service import request_verification

        await request_verification(
            incident=incident,
            policy=policy,
            db=db,
        )


# ──────────────────────────────────────────────────────────────────────────────
# CORE ESCALATION — executes the configured policy
# ──────────────────────────────────────────────────────────────────────────────


async def execute_escalation(
    incident: EmergencyIncident,
    user: UserRead,
    policy: EmergencyPolicy,
    db: AsyncSession,
) -> EmergencyIncident:
    """
    Execute the user's emergency policy:
    1. Transition to ESCALATING
    2. Check consent for escalation
    3. Notify primary contacts
    4. Share location if consented
    5. Notify secondary contacts if policy requires
    """
    incident = await update_incident_status(incident, "ESCALATING", db)

    await log_event(
        db,
        incident.id,
        "ESCALATED",
        "Escalation started. Executing emergency policy.",
        {
            "policy_auto_escalate": policy.auto_escalate,
            "notify_primary": policy.notify_primary_on_no_response,
            "notify_secondary": policy.notify_secondary_on_no_response,
            "share_location": policy.share_location_on_escalation,
        },
    )

    # ── Consent check for auto-escalation ─────────────────────────────────────
    # Manual SOS bypasses this check (user explicitly triggered).
    if incident.trigger_type != "MANUAL_SOS":
        can_escalate = await consent_service.can_auto_escalate(incident.user_id, db)
        if not can_escalate:
            await log_event(
                db,
                incident.id,
                "CONSENT_DENIED",
                "Auto-escalation blocked: user has not consented to automatic escalation.",
            )
            return incident

    # ── Notify primary contacts ────────────────────────────────────────────────
    if policy.notify_primary_on_no_response:
        primary_contacts = await contact_service.get_primary_contacts(incident.user_id, db)
        await _notify_contacts(
            contacts=primary_contacts,
            incident=incident,
            user=user,
            db=db,
        )

    # ── Location sharing ───────────────────────────────────────────────────────
    if policy.share_location_on_escalation:
        can_share = await consent_service.can_share_location(incident.user_id, db)
        if can_share:
            await _start_location_sharing(incident=incident, db=db)
        else:
            await log_event(
                db,
                incident.id,
                "CONSENT_DENIED",
                "Location sharing blocked: user has not consented to location sharing.",
            )

    # ── Notify secondary contacts ──────────────────────────────────────────────
    if policy.notify_secondary_on_no_response:
        all_contacts = await contact_service.get_trusted_contacts(incident.user_id, db)
        secondary = [c for c in all_contacts if not c.is_primary]
        if secondary:
            await _notify_contacts(
                contacts=secondary,
                incident=incident,
                user=user,
                db=db,
            )

    return incident


# ──────────────────────────────────────────────────────────────────────────────
# NO-RESPONSE PATH — called from Celery task on verification timeout
# ──────────────────────────────────────────────────────────────────────────────


async def execute_no_response_escalation(
    incident: EmergencyIncident,
    db: AsyncSession,
) -> None:
    """
    Called when the user does not respond to verification within the policy timeout.

    Loads a minimal user representation (enough for notifications) and
    executes the escalation policy.
    """
    await log_event(
        db,
        incident.id,
        "NO_RESPONSE",
        "User did not respond within the configured timeout. Auto-escalating.",
    )

    from app.services.policy_service import get_policy_or_default

    policy = await get_policy_or_default(incident.user_id, db)

    # Build a minimal UserRead so notification service has a name
    # In production BE1 will have a real user service; use what we have.
    from sqlalchemy import select

    from app.models.user import User

    result = await db.execute(select(User).where(User.id == incident.user_id))
    user_row = result.scalar_one_or_none()

    from app.schemas.user import UserRead

    if user_row:
        user = UserRead(
            id=user_row.id,
            full_name=user_row.full_name,
            email=user_row.email,
            phone_number=user_row.phone_number,
        )
    else:
        # Fallback if user row is missing (should never happen in production)
        user = UserRead(
            id=incident.user_id,
            full_name="ARIA User",
            email="unknown@aria.app",
        )

    await execute_escalation(
        incident=incident,
        user=user,
        policy=policy,
        db=db,
    )


# ──────────────────────────────────────────────────────────────────────────────
# INTERNAL HELPERS
# ──────────────────────────────────────────────────────────────────────────────


async def _notify_contacts(
    contacts: list[TrustedContact],
    incident: EmergencyIncident,
    user: UserRead,
    db: AsyncSession,
) -> None:
    """Dispatch emergency alerts to a list of trusted contacts."""
    from app.services.notifications.dispatcher import notification_dispatcher

    for contact in contacts:
        try:
            await notification_dispatcher.send_guardian_alert(
                contact=contact,
                incident=incident,
                user=user,
            )
            await log_event(
                db,
                incident.id,
                "CONTACT_NOTIFIED",
                f"Emergency alert sent to contact: {contact.name}.",
                {
                    "contact_id": str(contact.id),
                    "contact_name": contact.name,
                    "is_primary": contact.is_primary,
                },
            )

            # Broadcast to guardian's WebSocket channel if connected
            from app.websocket.manager import ws_manager

            await ws_manager.broadcast_to_incident(
                str(incident.id),
                {
                    "event": "contact_notified",
                    "incident_id": str(incident.id),
                    "contact_name": contact.name,
                    "timestamp": datetime.now(UTC).isoformat(),
                },
            )
        except Exception as exc:  # noqa: BLE001
            # Notification failure must never crash the escalation pipeline
            await log_event(
                db,
                incident.id,
                "CONTACT_NOTIFIED",
                f"Failed to notify contact {contact.name}: {exc}",
                {"contact_id": str(contact.id), "error": str(exc), "success": False},
            )


async def _start_location_sharing(
    incident: EmergencyIncident,
    db: AsyncSession,
) -> None:
    """Log location-sharing-started event and broadcast to guardians."""
    await log_event(
        db,
        incident.id,
        "LOCATION_SHARING_STARTED",
        "Live location sharing started. Authorized guardians will receive updates.",
        {
            "has_initial_location": incident.latitude is not None,
            "latitude": incident.latitude,
            "longitude": incident.longitude,
        },
    )

    from app.websocket.manager import ws_manager

    await ws_manager.broadcast_to_incident(
        str(incident.id),
        {
            "event": "location_sharing_started",
            "incident_id": str(incident.id),
            "timestamp": datetime.now(UTC).isoformat(),
        },
    )
