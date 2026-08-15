"""eBay Browse API provider; no HTML scraping or protection bypassing."""

from __future__ import annotations

import base64
import os
from collections.abc import Mapping
from typing import Any

import httpx

from dealfinder.config import SearchCriteria, SiteConfig
from dealfinder.models import HardwareListing
from dealfinder.normalization import normalize_listing
from dealfinder.providers.base import (
    HardwareProvider,
    ProviderUnavailable,
)
from dealfinder.providers.http import ResilientHttpClient
from dealfinder.providers.registry import register_provider

TOKEN_URL = "https://api.ebay.com/identity/v1/oauth2/token"
SEARCH_URL = "https://api.ebay.com/buy/browse/v1/item_summary/search"


@register_provider("ebay")
def build_ebay_provider(config: SiteConfig) -> HardwareProvider:
    return EbayProvider(config)


class EbayProvider(HardwareProvider):
    name = "ebay"

    def __init__(
        self,
        config: SiteConfig,
        *,
        client_id: str | None = None,
        client_secret: str | None = None,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        super().__init__(config)
        self.client_id = client_id or os.getenv("EBAY_CLIENT_ID")
        self.client_secret = client_secret or os.getenv("EBAY_CLIENT_SECRET")
        self.client = client

    async def search(self, criteria: SearchCriteria) -> list[HardwareListing]:
        if not self.client_id or not self.client_secret:
            raise ProviderUnavailable(
                "set EBAY_CLIENT_ID and EBAY_CLIENT_SECRET to enable the eBay Browse API"
            )
        client = ResilientHttpClient(self.name, self.config, client=self.client)
        try:
            token = await self._token(client)
            response = await client.request(
                "GET",
                SEARCH_URL,
                headers={
                    "Authorization": f"Bearer {token}",
                    "X-EBAY-C-MARKETPLACE-ID": str(
                        self.config.settings.get("marketplace_id", "EBAY_US")
                    ),
                },
                params={
                    "q": criteria.query or " ".join(criteria.cpu.preferred_models[:3]),
                    "limit": str(self.config.max_listings),
                },
                cache_ttl_seconds=float(self.config.settings.get("response_cache_seconds", 300)),
            )
            return [self._normalize(item) for item in response.json().get("itemSummaries", [])]
        finally:
            await client.aclose()

    async def _token(self, client: ResilientHttpClient) -> str:
        credentials = base64.b64encode(f"{self.client_id}:{self.client_secret}".encode()).decode()
        response = await client.request(
            "POST",
            TOKEN_URL,
            headers={
                "Authorization": f"Basic {credentials}",
                "Content-Type": "application/x-www-form-urlencoded",
            },
            data={
                "grant_type": "client_credentials",
                "scope": "https://api.ebay.com/oauth/api_scope",
            },
        )
        token = response.json().get("access_token")
        if not token:
            raise ProviderUnavailable("eBay OAuth response did not contain an access token")
        return str(token)

    def _normalize(self, item: Mapping[str, Any]) -> HardwareListing:
        shipping_options = item.get("shippingOptions") or []
        shipping = "0"
        if shipping_options:
            shipping = shipping_options[0].get("shippingCost", {}).get("value", "0")
        seller = item.get("seller") or {}
        availability = item.get("estimatedAvailabilities") or []
        quantity = availability[0].get("estimatedAvailableQuantity") if availability else None
        price = item.get("price") or {}
        return normalize_listing(
            self.name,
            {
                "id": item.get("itemId"),
                "title": item["title"],
                "url": item["itemWebUrl"],
                "price": price["value"],
                "currency": price.get("currency", "USD"),
                "shipping": shipping,
                "condition": item.get("condition"),
                "quantity": int(quantity) if quantity is not None else None,
                "seller_name": seller.get("username"),
                "seller_rating_percent": seller.get("feedbackPercentage"),
                "seller_feedback_count": seller.get("feedbackScore"),
            },
        )
