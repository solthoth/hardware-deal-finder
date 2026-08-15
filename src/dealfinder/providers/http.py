"""Shared responsible HTTP behavior for provider adapters."""

from __future__ import annotations

import asyncio
import time
from collections.abc import Awaitable, Callable, Mapping
from dataclasses import dataclass
from typing import Any

import httpx

from dealfinder.config import SiteConfig
from dealfinder.providers.base import ProviderRateLimited, ProviderUnavailable

USER_AGENT = "hardware-deal-finder/0.2 (+https://github.com/solthoth/hardware-deal-finder)"
Sleep = Callable[[float], Awaitable[None]]


@dataclass(frozen=True)
class CacheEntry:
    expires_at: float
    response: httpx.Response


class ResilientHttpClient:
    """Rate-limited client with bounded retries, backoff, and opt-in GET caching."""

    def __init__(
        self,
        provider_name: str,
        config: SiteConfig,
        *,
        client: httpx.AsyncClient | None = None,
        sleep: Sleep = asyncio.sleep,
    ) -> None:
        self.provider_name = provider_name
        self.config = config
        self._owns_client = client is None
        self._client = client or httpx.AsyncClient(
            timeout=config.request_timeout_seconds,
            headers={"User-Agent": USER_AGENT},
        )
        self._sleep = sleep
        self._last_request_at = 0.0
        self._rate_lock = asyncio.Lock()
        self._cache: dict[str, CacheEntry] = {}

    async def aclose(self) -> None:
        if self._owns_client:
            await self._client.aclose()

    async def request(
        self,
        method: str,
        url: str,
        *,
        cache_ttl_seconds: float = 0,
        **kwargs: Any,
    ) -> httpx.Response:
        cache_key = self._cache_key(method, url, kwargs)
        cached = self._cache.get(cache_key)
        now = time.monotonic()
        if cached and cached.expires_at > now:
            return cached.response
        response = await self._request_with_retries(method, url, **kwargs)
        if method.upper() == "GET" and cache_ttl_seconds > 0:
            self._cache[cache_key] = CacheEntry(now + cache_ttl_seconds, response)
        return response

    async def _request_with_retries(self, method: str, url: str, **kwargs: Any) -> httpx.Response:
        retries = int(self.config.settings.get("max_retries", 2))
        for attempt in range(retries + 1):
            await self._wait_for_rate_limit()
            try:
                response = await self._client.request(method, url, **kwargs)
            except httpx.HTTPError as error:
                if attempt == retries:
                    raise ProviderUnavailable(
                        f"{self.provider_name} request failed after retries: {error}"
                    ) from error
                await self._sleep(2**attempt)
                continue
            if response.status_code == 429:
                if attempt == retries:
                    raise ProviderRateLimited(
                        f"{self.provider_name} rate limited requests after retries"
                    )
                await self._sleep(self._retry_delay(response, attempt))
                continue
            if response.status_code >= 500:
                if attempt == retries:
                    raise ProviderUnavailable(
                        f"{self.provider_name} remained unavailable (HTTP {response.status_code})"
                    )
                await self._sleep(2**attempt)
                continue
            if response.is_error:
                raise ProviderUnavailable(
                    f"{self.provider_name} returned HTTP {response.status_code}"
                )
            return response
        raise ProviderUnavailable(f"{self.provider_name} request failed")

    async def _wait_for_rate_limit(self) -> None:
        interval = 1 / self.config.rate_limit_per_second
        async with self._rate_lock:
            remaining = interval - (time.monotonic() - self._last_request_at)
            if remaining > 0:
                await self._sleep(remaining)
            self._last_request_at = time.monotonic()

    @staticmethod
    def _retry_delay(response: httpx.Response, attempt: int) -> float:
        value = response.headers.get("Retry-After")
        if value:
            try:
                return min(float(value), 60.0)
            except ValueError:
                pass
        return float(2**attempt)

    @staticmethod
    def _cache_key(method: str, url: str, kwargs: Mapping[str, Any]) -> str:
        params = kwargs.get("params")
        return f"{method.upper()}:{url}:{params!r}"
