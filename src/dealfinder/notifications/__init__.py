"""Built-in notification plugins."""

from dealfinder.notifications import console as console
from dealfinder.notifications.base import NotificationProvider
from dealfinder.notifications.registry import create_notification_provider

__all__ = ["NotificationProvider", "create_notification_provider"]
