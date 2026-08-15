"""Provider registration and configuration-driven construction."""

from __future__ import annotations

from collections.abc import Callable, Iterable
from importlib import metadata
from typing import Any, Protocol, cast

from dealfinder.config import SearchCriteria, SiteConfig, SitesConfig
from dealfinder.models import HardwareListing
from dealfinder.providers.base import HardwareProvider, ProviderUnsupported

ProviderFactory = Callable[[SiteConfig], HardwareProvider]
_FACTORIES: dict[str, ProviderFactory] = {}
ENTRY_POINT_GROUP = "dealfinder.providers"


class ProviderEntryPoint(Protocol):
    name: str

    def load(self) -> Any: ...


def register_provider(name: str) -> Callable[[ProviderFactory], ProviderFactory]:
    def decorator(factory: ProviderFactory) -> ProviderFactory:
        if name in _FACTORIES:
            raise ValueError(f"provider already registered: {name}")
        _FACTORIES[name] = factory
        return factory

    return decorator


class UnsupportedProvider(HardwareProvider):
    def __init__(self, name: str, config: SiteConfig) -> None:
        super().__init__(config)
        self.name = name

    async def search(self, criteria: SearchCriteria) -> list[HardwareListing]:
        raise ProviderUnsupported(f"provider {self.name!r} has no registered integration")


def discover_provider_plugins(
    entry_points: Iterable[ProviderEntryPoint] | None = None,
) -> None:
    """Load third-party provider factories from Python package entry points."""

    discovered = entry_points or metadata.entry_points(group=ENTRY_POINT_GROUP)
    for entry_point in discovered:
        if entry_point.name in _FACTORIES:
            continue
        loaded = entry_point.load()
        if not callable(loaded):
            raise TypeError(f"provider entry point {entry_point.name!r} is not callable")
        _FACTORIES[entry_point.name] = cast(ProviderFactory, loaded)


def create_enabled_providers(config: SitesConfig) -> list[HardwareProvider]:
    discover_provider_plugins()
    providers: list[HardwareProvider] = []
    for name, site in config.sites.items():
        if not site.enabled:
            continue
        configured_site = site.model_copy(update={"name": name})
        factory = _FACTORIES.get(site.provider or name)
        providers.append(
            factory(configured_site) if factory else UnsupportedProvider(name, configured_site)
        )
    return providers
