"""Deterministic provider for tests and offline demonstrations."""

from __future__ import annotations

from dealfinder.config import SearchCriteria, SiteConfig
from dealfinder.models import HardwareListing
from dealfinder.providers.base import HardwareProvider


class FixtureProvider(HardwareProvider):
    name = "fixture"

    def __init__(self, config: SiteConfig, listings: list[HardwareListing]) -> None:
        super().__init__(config)
        self.listings = listings

    async def search(self, criteria: SearchCriteria) -> list[HardwareListing]:
        return self.listings[: self.config.max_listings]
