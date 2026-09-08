"""
ARIA / SAKHI — Twilio SMS Notification Channel
================================================
BE3 OWNS THIS FILE.

Sends SMS via Twilio. Only active when SMS_NOTIFICATIONS_ENABLED=true in .env.
If not configured, is_available() returns False — channel is silently skipped.
"""

import logging

from app.services.notifications.base import (
    NotificationChannel,
    NotificationMessage,
    NotificationRecipient,
)

logger = logging.getLogger(__name__)


class SMSChannel(NotificationChannel):
    """Twilio SMS channel for emergency alerts."""

    @property
    def channel_name(self) -> str:
        return "sms"

    async def is_available(self) -> bool:
        from app.config import get_settings

        settings = get_settings()
        return (
            settings.SMS_NOTIFICATIONS_ENABLED
            and bool(settings.TWILIO_ACCOUNT_SID)
            and bool(settings.TWILIO_AUTH_TOKEN)
            and bool(settings.TWILIO_FROM_NUMBER)
        )

    async def send(
        self,
        recipient: NotificationRecipient,
        message: NotificationMessage,
    ) -> bool:
        if not recipient.phone_number:
            logger.debug("SMS skipped for %s: no phone number.", recipient.name)
            return False

        if not await self.is_available():
            logger.debug("SMS channel not configured — skipping.")
            return False

        try:
            from twilio.rest import Client as TwilioClient

            from app.config import get_settings

            settings = get_settings()
            client = TwilioClient(settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN)

            sms_body = f"{message.title}\n\n{message.body}"
            if len(sms_body) > 1600:
                sms_body = sms_body[:1597] + "..."

            twilio_msg = client.messages.create(
                body=sms_body,
                from_=settings.TWILIO_FROM_NUMBER,
                to=recipient.phone_number,
            )
            logger.info(
                "SMS sent to %s (%s). SID: %s",
                recipient.name,
                recipient.phone_number,
                twilio_msg.sid,
            )
            return True

        except Exception as exc:  # noqa: BLE001
            logger.error("SMS failed for %s: %s", recipient.name, exc)
            return False
