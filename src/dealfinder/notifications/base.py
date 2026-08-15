"""Notification plugin contract."""

from __future__ import annotations

from abc import ABC, abstractmethod

from dealfinder.watch import DealEvent


class NotificationProvider(ABC):
    name: str

    @abstractmethod
    async def notify(self, events: list[DealEvent]) -> None:
        """Deliver zero or more deal events."""
