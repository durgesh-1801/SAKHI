"""
ARIA / SAKHI — In-App Notification Channel
============================================
BE3 OWNS THIS FILE.

Stores notifications in the database for in-app display.
Always available — no external provider needed.

The mobile app polls or subscribes (via WebSocket) to receive these.
"""

import logging
import uuid
from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from app.services.notifications.base import (
    NotificationChannel,
    NotificationMessage,
    NotificationRecipient,
)

logger = logging.getLogger(__name__)


class InAppNotificationChannel(NotificationChannel):
    """
    In-app notification channel.

    Stores notifications in a lightweight in-memory log (for now).
    In production this should persist to a `notifications` table
    that BE2 or BE1 may own — coordinate with the team.

    For the current greenfield state, we use a module-level list
    so tests can inspect delivered notifications without a DB.
    This is intentionally simple and replaceable.
    """

    # Module-level store — replace with DB persistence when ready
    _store: list[dict] = []

    @property
    def channel_name(self) -> str:
        return "in_app"

    async def is_available(self) -> bool:
        return True  # Always available

    async def send(
        self,
        recipient: NotificationRecipient,
        message: NotificationMessage,
    ) -> bool:
        record = {
            "id": str(uuid.uuid4()),
            "user_id": recipient.user_id,
            "title": message.title,
            "body": message.body,
            "data": message.data,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "is_read": False,
        }
        self.__class__._store.append(record)
        logger.info(
            "In-app notification stored for user %s: %s",
            recipient.user_id,
            message.title,
        )
        return True

    @classmethod
    def get_notifications_for_user(cls, user_id: str) -> list[dict]:
        """Return stored notifications for a user (for tests/polling endpoint)."""
        return [n for n in cls._store if n["user_id"] == user_id]

    @classmethod
    def clear_store(cls) -> None:
        """Test helper — clear the in-memory store between tests."""
        cls._store.clear()
