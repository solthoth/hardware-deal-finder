from __future__ import annotations

from typing import Any

import httpx
import pytest

from dealfinder.config import SearchConfig, SiteConfig, SitesConfig
from dealfinder.providers.base import ProviderUnsupported
from dealfinder.providers.generic import GenericJsonProvider
from dealfinder.providers.http import ResilientHttpClient
from dealfinder.providers.registry import create_enabled_providers
from dealfinder.service import ProviderStatus, SearchService


@pytest.mark.asyncio
async def test_http_client_retries_and_caches_successful_gets() -> None:
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        if calls == 1:
            return httpx.Response(503)
        return httpx.Response(200, json={"items": []})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as raw_client:
        client = ResilientHttpClient(
            "test",
            SiteConfig(rate_limit_per_second=10_000),
            client=raw_client,
            sleep=lambda _: _completed_sleep(),
        )
        first = await client.request("GET", "https://example.test/feed", cache_ttl_seconds=60)
        second = await client.request("GET", "https://example.test/feed", cache_ttl_seconds=60)
    assert first.json() == second.json() == {"items": []}
    assert calls == 2


async def _completed_sleep() -> None:
    return None


@pytest.mark.asyncio
async def test_generic_json_provider_uses_configured_documented_feed(
    search_config: SearchConfig,
) -> None:
    payload: dict[str, Any] = {
        "results": [
            {
                "sku": "mini-1",
                "name": "Acme Mini Ryzen 5 PRO 5650GE 16GB 512GB NVMe",
                "link": "https://catalog.example.test/mini-1",
                "offer": {"price": "275.00", "shipping": "0"},
                "stock": 4,
            }
        ]
    }

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.params["query"] == search_config.search.query
        return httpx.Response(200, json=payload)

    config = SiteConfig(
        rate_limit_per_second=10_000,
        settings={
            "endpoint": "https://catalog.example.test/search",
            "query_parameter": "query",
            "items_path": "results",
            "field_map": {
                "id": "sku",
                "title": "name",
                "url": "link",
                "price": "offer.price",
                "shipping": "offer.shipping",
                "quantity": "stock",
            },
        },
    )
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        listings = await GenericJsonProvider(config, client=client).search(search_config.search)
    assert len(listings) == 1
    assert listings[0].listing_id == "mini-1"
    assert listings[0].quantity_available == 4


@pytest.mark.parametrize("name", ["minisforum", "lenovo", "dell", "hp", "newegg"])
@pytest.mark.asyncio
async def test_researched_store_adapters_report_unsupported_access(
    name: str, search_config: SearchConfig
) -> None:
    providers = create_enabled_providers(SitesConfig(sites={name: SiteConfig(enabled=True)}))
    assert providers[0].name == name
    with pytest.raises(ProviderUnsupported, match="documented"):
        await providers[0].search(search_config.search)


@pytest.mark.asyncio
async def test_service_distinguishes_unsupported_from_temporary_unavailability(
    search_config: SearchConfig,
) -> None:
    provider = create_enabled_providers(
        SitesConfig(sites={"minisforum": SiteConfig(enabled=True)})
    )[0]
    result = await SearchService.from_config(search_config, [provider]).search()
    assert result.provider_results["minisforum"].status is ProviderStatus.UNSUPPORTED
