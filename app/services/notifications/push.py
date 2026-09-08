"""
ARIA / SAKHI — Firebase FCM Push Notification Channel
======================================================
BE3 OWNS THIS FILE.

Sends push notifications via Firebase Cloud Messaging.
Requires FIREBASE_CREDENTIALS_PATH or FIREBASE_CREDENTIALS_JSON in .env.

If Firebase is not configured, is_available() returns False and
the dispatcher skips this channel gracefully.
"""

import json
import logging

from app.services.notifications.base import (
    NotificationChannel,
    NotificationMessage,
    NotificationRecipient,
)

logger = logging.getLogger(__name__)

_firebase_initialized = False


def _init_firebase() -> bool:
    """Initialize Firebase Admin SDK once. Returns True if successful."""
    global _firebase_initialized  # noqa: PLW0603
    if _firebase_initialized:
        return True

    try:
        import firebase_admin
        from firebase_admin import credentials

        from app.config import get_settings

        settings = get_settings()

        if firebase_admin._apps:  # type: ignore[attr-defined]
            _firebase_initialized = True
            return True

        if settings.FIREBASE_CREDENTIALS_JSON:
            cred_dict = json.loads(settings.FIREBASE_CREDENTIALS_JSON)
            cred = credentials.Certificate(cred_dict)
        elif settings.FIREBASE_CREDENTIALS_PATH:
            import os

            if not os.path.exists(settings.FIREBASE_CREDENTIALS_PATH):
                logger.warning(
                    "Firebase credentials file not found: %s",
                    settings.FIREBASE_CREDENTIALS_PATH,
                )
                return False
            cred = credentials.Certificate(settings.FIREBASE_CREDENTIALS_PATH)
        else:
            return False

        firebase_admin.initialize_app(cred)
        _firebase_initialized = True
        logger.info("Firebase Admin SDK initialized successfully.")
        return True

    except Exception as exc:  # noqa: BLE001
        logger.warning("Firebase initialization failed: %s", exc)
        return False


class PushNotificationChannel(NotificationChannel):
    """Firebase FCM push notification channel."""

    @property
    def channel_name(self) -> str:
        return "push"

    async def is_available(self) -> bool:
        return _init_firebase()

    async def send(
        self,
        recipient: NotificationRecipient,
        message: NotificationMessage,
    ) -> bool:
        if not recipient.fcm_token:
            logger.debug("Push skipped for recipient %s: no FCM token.", recipient.name)
            return False

        if not await self.is_available():
            return False

        try:
            from firebase_admin import messaging

            fcm_message = messaging.Message(
                notification=messaging.Notification(
                    title=message.title,
                    body=message.body,
                    image=message.image_url,
                ),
                data={k: str(v) for k, v in message.data.items()},
                token=recipient.fcm_token,
                android=messaging.AndroidConfig(
                    priority="high",
                    notification=messaging.AndroidNotification(
                        sound="emergency_alert",
                        channel_id="aria_emergency",
                    ),
                ),
                apns=messaging.APNSConfig(
                    payload=messaging.APNSPayload(
                        aps=messaging.Aps(
                            sound=messaging.CriticalSound(
                                critical=True,
                                name="emergency_alert.caf",
                                volume=1.0,
                            ),
                            badge=1,
                        )
                    )
                ),
            )

            response = messaging.send(fcm_message)
            logger.info(
                "Push sent to %s. FCM message ID: %s", recipient.name, response
            )
            return True

        except Exception as exc:  # noqa: BLE001
            logger.error("Push notification failed for %s: %s", recipient.name, exc)
            return False
