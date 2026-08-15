"""Configurable adapter for documented JSON catalog or search feeds."""

from __future__ import annotations

import os
from collections.abc import Mapping
from typing import Any

import httpx

from dealfinder.config import SearchCriteria, SiteConfig
from dealfinder.models import HardwareListing
from dealfinder.normalization import normalize_listing
from dealfinder.providers.base import HardwareProvider, ProviderUnavailable
from dealfinder.providers.http import ResilientHttpClient
from dealfinder.providers.registry import register_provider


@register_provider("generic")
def build_generic_provider(config: SiteConfig) -> HardwareProvider:
    return GenericJsonProvider(config)


def _path(value: Any, path: str) -> Any:
    current = value
    if not path:
        return current
    for part in path.split("."):
        if isinstance(current, list):
            current = current[int(part)]
        elif isinstance(current, Mapping):
            current = current.get(part)
        else:
            return None
    return current


class GenericJsonProvider(HardwareProvider):
    """Read a user-authorized, documented JSON feed through configured field paths."""

    name = "generic"

    def __init__(self, config: SiteConfig, *, client: httpx.AsyncClient | None = None) -> None:
        super().__init__(config)
        self._client = ResilientHttpClient(self.name, config, client=client)

    async def search(self, criteria: SearchCriteria) -> list[HardwareListing]:
        endpoint = self.config.settings.get("endpoint")
        if not isinstance(endpoint, str):
            raise ProviderUnavailable("generic provider requires settings.endpoint")
        if not endpoint.startswith("https://") and not self.config.settings.get(
            "allow_insecure_http"
        ):
            raise ProviderUnavailable("generic provider endpoint must use HTTPS")
        headers = self._headers_from_environment()
        query_parameter = self.config.settings.get("query_parameter")
        params = (
            {str(query_parameter): criteria.query or criteria.category} if query_parameter else None
        )
        try:
            response = await self._client.request(
                "GET",
                endpoint,
                headers=headers,
                params=params,
                cache_ttl_seconds=float(self.config.settings.get("response_cache_seconds", 300)),
            )
            return self._normalize_response(response.json())
        except (TypeError, ValueError, KeyError, IndexError) as error:
            raise ProviderUnavailable(
                f"generic provider response is incompatible: {error}"
            ) from error
        finally:
            await self._client.aclose()

    def _headers_from_environment(self) -> dict[str, str]:
        configured = self.config.settings.get("headers_from_env", {})
        if not isinstance(configured, Mapping):
            raise ProviderUnavailable("generic settings.headers_from_env must be a mapping")
        headers: dict[str, str] = {}
        for header, variable in configured.items():
            value = os.getenv(str(variable))
            if not value:
                raise ProviderUnavailable(
                    f"generic provider requires environment variable {variable}"
                )
            headers[str(header)] = value
        return headers

    def _normalize_response(self, payload: Any) -> list[HardwareListing]:
        items = _path(payload, str(self.config.settings.get("items_path", "")))
        field_map = self.config.settings.get("field_map", {})
        if not isinstance(items, list) or not isinstance(field_map, Mapping):
            raise ValueError("configured items path or field map is invalid")
        listings: list[HardwareListing] = []
        for item in items[: self.config.max_listings]:
            canonical = {
                str(target): _path(item, str(source)) for target, source in field_map.items()
            }
            listings.append(normalize_listing(self.name, canonical))
        return listings
