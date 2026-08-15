from __future__ import annotations

import json
from typing import Any

import httpx
import pytest

from dealfinder.config import SearchConfig, SearchCriteria, SiteConfig
from dealfinder.models import HardwareListing
from dealfinder.providers.base import (
    HardwareProvider,
    ProviderUnavailable,
)
from dealfinder.providers.ebay import EbayProvider
from dealfinder.providers.fixture import FixtureProvider
from dealfinder.service import ProviderStatus, SearchService


def test_provider_interface_is_abstract() -> None:
    with pytest.raises(TypeError):
        HardwareProvider(SiteConfig())  # type: ignore[abstract]


@pytest.mark.asyncio
async def test_ebay_provider_requires_credentials(search_config: SearchConfig) -> None:
    provider = EbayProvider(SiteConfig(), client_id=None, client_secret=None)
    with pytest.raises(ProviderUnavailable, match="EBAY_CLIENT_ID"):
        await provider.search(search_config.search)


@pytest.mark.asyncio
async def test_ebay_provider_normalizes_mocked_browse_api(search_config: SearchConfig) -> None:
    requests: list[httpx.Request] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        if request.url.path.endswith("oauth2/token"):
            return httpx.Response(200, json={"access_token": "token", "expires_in": 7200})
        payload: dict[str, Any] = {
            "itemSummaries": [
                {
                    "itemId": "v1|123|0",
                    "title": "Lenovo M75q Gen 2 Ryzen 5 PRO 5650GE 16GB 256GB NVMe",
                    "itemWebUrl": "https://www.ebay.com/itm/123",
                    "price": {"value": "249.00", "currency": "USD"},
                    "shippingOptions": [{"shippingCost": {"value": "12.00"}}],
                    "condition": "Used",
                    "seller": {
                        "username": "trusted",
                        "feedbackPercentage": "99.8",
                        "feedbackScore": 2000,
                    },
                }
            ]
        }
        return httpx.Response(200, content=json.dumps(payload))

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        provider = EbayProvider(
            SiteConfig(max_listings=10, rate_limit_per_second=10_000),
            client_id="id",
            client_secret="secret",
            client=client,
        )
        listings = await provider.search(search_config.search)

    assert len(listings) == 1
    assert listings[0].provider == "ebay"
    assert listings[0].total_price == 261
    assert any(request.headers.get("authorization") == "Bearer token" for request in requests)


class FailingProvider(HardwareProvider):
    name = "failing"

    async def search(self, criteria: SearchCriteria) -> list[HardwareListing]:
        raise ProviderUnavailable("scheduled maintenance")


@pytest.mark.asyncio
async def test_service_isolates_provider_failure_and_ranks_success(
    search_config: SearchConfig, good_listing: HardwareListing
) -> None:
    providers = [
        FailingProvider(SiteConfig()),
        FixtureProvider(SiteConfig(), listings=[good_listing]),
    ]
    result = await SearchService.from_config(search_config, providers).search()
    assert result.provider_results["failing"].status is ProviderStatus.UNAVAILABLE
    assert result.provider_results["fixture"].listing_count == 1
    assert len(result.ranked) == 1
    assert result.ranked[0].listing.listing_id == "1"
