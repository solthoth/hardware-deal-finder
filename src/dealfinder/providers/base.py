"""Provider contracts and errors."""

from __future__ import annotations

from abc import ABC, abstractmethod

from dealfinder.config import SearchCriteria, SiteConfig
from dealfinder.models import HardwareListing


class ProviderError(RuntimeError):
    """Base class for expected provider failures."""


class ProviderUnavailable(ProviderError):
    """The provider cannot currently be queried safely."""


class ProviderRateLimited(ProviderError):
    """The provider exhausted its retry budget after rate limiting."""


class HardwareProvider(ABC):
    """Marketplace plugin interface."""

    name: str

    def __init__(self, config: SiteConfig) -> None:
        self.config = config

    @property
    def trust_weight(self) -> float:
        return self.config.trust_weight

    @abstractmethod
    async def search(self, criteria: SearchCriteria) -> list[HardwareListing]:
        """Return normalized listings or raise an expected ProviderError."""
