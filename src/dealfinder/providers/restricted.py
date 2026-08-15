"""Researched marketplace adapters without a safe public deal-search API."""

from __future__ import annotations

from functools import partial

from dealfinder.config import SearchCriteria, SiteConfig
from dealfinder.models import HardwareListing
from dealfinder.providers.base import HardwareProvider, ProviderUnsupported
from dealfinder.providers.registry import register_provider

ACCESS_LIMITATIONS: dict[str, tuple[str, str]] = {
    "amazon": (
        "the documented Product Advertising API was deprecated in favor of the gated "
        "Creators API; no Creators API credentials or stable public contract are configured",
        "https://affiliate-program.amazon.com/creatorsapi/docs/en-us/introduction",
    ),
    "minisforum": (
        "no documented public catalog or search API is available",
        "https://store.minisforum.com/",
    ),
    "lenovo": (
        "no documented public Outlet search API is available, and robots rules disallow "
        "internal search URLs",
        "https://www.lenovo.com/robots.txt",
    ),
    "dell": (
        "the documented Premier Catalog API requires a Dell B2B account and is not a public "
        "Outlet deal-search API",
        "https://developer.dell.com/apis",
    ),
    "hp": (
        "no documented public store search API is available, and robots rules disallow store "
        "API and search paths",
        "https://www.hp.com/robots.txt",
    ),
    "newegg": (
        "the documented Marketplace API manages seller inventory and is not a public consumer "
        "catalog search API",
        "https://developer.newegg.com/newegg_marketplace_api/",
    ),
    "backmarket": (
        "no documented public consumer catalog search API is available",
        "https://www.backmarket.com/",
    ),
}


class RestrictedMarketplaceProvider(HardwareProvider):
    def __init__(self, name: str, reason: str, documentation_url: str, config: SiteConfig) -> None:
        super().__init__(config)
        self.name = name
        self.reason = reason
        self.documentation_url = documentation_url

    async def search(self, criteria: SearchCriteria) -> list[HardwareListing]:
        raise ProviderUnsupported(
            f"{self.name} has no supported documented deal-search integration: {self.reason}; "
            f"see {self.documentation_url}"
        )


for _name, (_reason, _documentation_url) in ACCESS_LIMITATIONS.items():
    register_provider(_name)(
        partial(RestrictedMarketplaceProvider, _name, _reason, _documentation_url)
    )
