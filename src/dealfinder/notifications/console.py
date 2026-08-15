"""Console notification channel for CronJobs, logs, and shell automation."""

from __future__ import annotations

import json
from collections.abc import Callable

from dealfinder.notifications.base import NotificationProvider
from dealfinder.notifications.registry import register_notification_provider
from dealfinder.watch import DealEvent


@register_notification_provider("console")
def build_console_notification(output_format: str) -> NotificationProvider:
    return ConsoleNotificationProvider(output_format)


class ConsoleNotificationProvider(NotificationProvider):
    name = "console"

    def __init__(self, output_format: str, *, writer: Callable[[str], None] = print) -> None:
        self.output_format = output_format
        self.writer = writer

    async def notify(self, events: list[DealEvent]) -> None:
        if self.output_format == "json":
            self.writer(json.dumps([event.model_dump(mode="json") for event in events], indent=2))
            return
        if not events:
            self.writer("No new strong deals or material price drops detected.")
            return
        lines: list[str] = []
        for event in events:
            detail = f"{event.event_type.value}: {event.title} — ${event.current_price}"
            if event.price_drop_percent is not None:
                detail += f" ({event.price_drop_percent}% drop)"
            lines.extend([detail, str(event.url)])
        self.writer("\n".join(lines))
