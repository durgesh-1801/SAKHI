"""
ARIA / SAKHI — Notification Dispatcher
========================================
BE3 OWNS THIS FILE.

The single interface through which the emergency engine sends all notifications.
Routes to multiple channels in parallel; failures in one channel do not
block others.

Usage:
    from app.services.notifications.dispatcher import notification_dispatcher

    await notification_dispatcher.send_guardian_alert(contact, incident, user)
    await notification_dispatcher.send_verification_request(user_id, incident_id, ...)
"""

import logging
from datetime import UTC, datetime

from app.services.notifications.base import (
    NotificationChannel,
    NotificationMessage,
    NotificationRecipient,
)
from app.services.notifications.in_app import InAppNotificationChannel
from app.services.notifications.push import PushNotificationChannel
from app.services.notifications.sms import SMSChannel

logger = logging.getLogger(__name__)


class NotificationDispatcher:
    """
    Multi-channel notification dispatcher.

    All emergency notification logic flows through here, keeping
    the escalation service clean of provider-specific details.
    """

    def __init__(self, channels: list[NotificationChannel]) -> None:
        self._channels = channels

    async def _dispatch(
        self,
        recipient: NotificationRecipient,
        message: NotificationMessage,
    ) -> dict[str, bool]:
        """
        Send to all available channels. Returns a per-channel success map.
        Failures in one channel never raise — they are logged and recorded.
        """
        results: dict[str, bool] = {}
        for channel in self._channels:
            try:
                if await channel.is_available():
                    success = await channel.send(recipient, message)
                    results[channel.channel_name] = success
                else:
                    results[channel.channel_name] = False
            except Exception as exc:  # noqa: BLE001
                logger.error(
                    "Channel %s raised an unexpected error for %s: %s",
                    channel.channel_name,
                    recipient.name,
                    exc,
                )
                results[channel.channel_name] = False
        return results

    # ──────────────────────────────────────────────────────────────────────────
    # High-level emergency notification methods
    # ──────────────────────────────────────────────────────────────────────────

    async def send_verification_request(
        self,
        user_id: object,  # uuid.UUID — typed loosely to avoid circular imports
        incident_id: str,
        timeout_seconds: int,
        expires_at: str,
    ) -> None:
        """
        Send 'Are you safe?' prompt to the user.
        Delivered as a high-priority push + in-app notification.
        """
        recipient = NotificationRecipient(
            user_id=str(user_id),
            name="User",
        )
        message = NotificationMessage(
            title="🚨 ARIA Safety Check",
            body=(
                f"Are you safe? Please respond within {timeout_seconds} seconds. "
                "If you don't respond, your emergency contacts will be notified."
            ),
            data={
                "type": "VERIFICATION_REQUEST",
                "incident_id": incident_id,
                "expires_at": expires_at,
                "action": "open_verification",
            },
        )
        results = await self._dispatch(recipient, message)
        logger.info("Verification request dispatched. Results: %s", results)

    async def send_guardian_alert(
        self,
        contact: object,  # TrustedContact — typed loosely
        incident: object,  # EmergencyIncident — typed loosely
        user: object,  # UserRead — typed loosely
    ) -> None:
        """
        Send an emergency alert to a trusted contact / guardian.

        Only exposes information necessary for the emergency response —
        no unnecessary PII.
        """
        # Build recipient from contact fields
        recipient = NotificationRecipient(
            user_id=str(getattr(contact, "contact_user_id", None) or ""),
            name=getattr(contact, "name", "Contact"),
            phone_number=getattr(contact, "phone_number", None),
            email=getattr(contact, "email", None),
        )

        risk_level = getattr(incident, "risk_level", "CRITICAL")
        ai_reasons = getattr(incident, "ai_reasons", None) or []
        incident_id = str(getattr(incident, "id", ""))
        user_name = getattr(user, "full_name", "ARIA User")

        reason_text = ""
        if ai_reasons:
            reason_text = "\nReason: " + ", ".join(ai_reasons[:2])

        now = datetime.now(UTC).strftime("%I:%M %p")

        message = NotificationMessage(
            title="🚨 Emergency Alert — ARIA",
            body=(
                f"{user_name} may be in danger and needs your help.\n"
                f"Risk: {risk_level}\n"
                f"Time: {now}"
                f"{reason_text}"
            ),
            data={
                "type": "GUARDIAN_ALERT",
                "incident_id": incident_id,
                "user_name": user_name,
                "risk_level": risk_level,
                "action": "open_guardian_dashboard",
            },
        )
        results = await self._dispatch(recipient, message)
        logger.info(
            "Guardian alert dispatched to %s. Results: %s",
            getattr(contact, "name", "?"),
            results,
        )

    async def send_incident_resolved(
        self,
        contact: object,
        incident: object,
        user: object,
    ) -> None:
        """Notify a guardian that the emergency has been resolved."""
        recipient = NotificationRecipient(
            user_id=str(getattr(contact, "contact_user_id", None) or ""),
            name=getattr(contact, "name", "Contact"),
            phone_number=getattr(contact, "phone_number", None),
        )
        user_name = getattr(user, "full_name", "ARIA User")
        message = NotificationMessage(
            title="✅ Emergency Resolved — ARIA",
            body=f"{user_name}'s emergency has been resolved. They are safe.",
            data={
                "type": "INCIDENT_RESOLVED",
                "incident_id": str(getattr(incident, "id", "")),
            },
        )
        await self._dispatch(recipient, message)


# ── Singleton dispatcher instance used across the app ─────────────────────────
notification_dispatcher = NotificationDispatcher(
    channels=[
        PushNotificationChannel(),
        InAppNotificationChannel(),
        SMSChannel(),
    ]
)
