"""Notification provider registry."""

from __future__ import annotations

from collections.abc import Callable

from dealfinder.notifications.base import NotificationProvider

NotificationFactory = Callable[[str], NotificationProvider]
_FACTORIES: dict[str, NotificationFactory] = {}


def register_notification_provider(
    name: str,
) -> Callable[[NotificationFactory], NotificationFactory]:
    def decorator(factory: NotificationFactory) -> NotificationFactory:
        if name in _FACTORIES:
            raise ValueError(f"notification provider already registered: {name}")
        _FACTORIES[name] = factory
        return factory

    return decorator


def create_notification_provider(name: str, output_format: str) -> NotificationProvider:
    try:
        return _FACTORIES[name](output_format)
    except KeyError as error:
        raise ValueError(f"unknown notification provider: {name}") from error
