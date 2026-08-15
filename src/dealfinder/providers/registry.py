"""Provider registration and configuration-driven construction."""

from __future__ import annotations

from collections.abc import Callable

from dealfinder.config import SearchCriteria, SiteConfig, SitesConfig
from dealfinder.models import HardwareListing
from dealfinder.providers.base import HardwareProvider, ProviderUnavailable

ProviderFactory = Callable[[SiteConfig], HardwareProvider]
_FACTORIES: dict[str, ProviderFactory] = {}


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
        raise ProviderUnavailable(f"provider {self.name!r} is a configured placeholder")


def create_enabled_providers(config: SitesConfig) -> list[HardwareProvider]:
    providers: list[HardwareProvider] = []
    for name, site in config.sites.items():
        if not site.enabled:
            continue
        factory = _FACTORIES.get(name)
        providers.append(factory(site) if factory else UnsupportedProvider(name, site))
    return providers
