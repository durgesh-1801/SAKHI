"""
ARIA / SAKHI — Notification Abstraction Base
=============================================
BE3 OWNS THIS FILE.

Defines the NotificationChannel ABC and the NotificationMessage data class.
All channel implementations inherit from NotificationChannel.

This abstraction ensures the emergency engine is never tightly coupled
to a single notification provider.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


@dataclass
class NotificationRecipient:
    """Who should receive the notification."""

    user_id: str | None = None  # SAKHI user ID (if registered)
    name: str = "User"  # Display name for the message body
    fcm_token: str | None = None  # Firebase Cloud Messaging device token
    phone_number: str | None = None  # For SMS channel
    email: str | None = None  # For email channel


@dataclass
class NotificationMessage:
    """
    Notification payload.

    Title and body are required.
    data is an optional dict that is delivered as a silent data payload
    (useful for in-app deep-linking and structured handling).
    """

    title: str
    body: str
    data: dict[str, Any] = field(default_factory=dict)
    # Optional: override image / icon URL for push
    image_url: str | None = None


class NotificationChannel(ABC):
    """
    Abstract base class for all notification channels.

    Each channel implements `send` and `is_available`.
    The dispatcher routes to available channels based on configuration.
    """

    @property
    @abstractmethod
    def channel_name(self) -> str:
        """Human-readable channel identifier (e.g. 'push', 'sms', 'in_app')."""

    @abstractmethod
    async def is_available(self) -> bool:
        """
        Returns True if this channel is configured and operational.
        Used by the dispatcher to skip unconfigured channels gracefully.
        """

    @abstractmethod
    async def send(
        self,
        recipient: NotificationRecipient,
        message: NotificationMessage,
    ) -> bool:
        """
        Send a notification.

        Returns True on success, False on failure.
        Must NOT raise exceptions — failures are logged and handled by the dispatcher.
        """
