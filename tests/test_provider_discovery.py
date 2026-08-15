from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError

from dealfinder.config import SearchCriteria, SiteConfig, SitesConfig, load_sites_config
from dealfinder.models import HardwareListing
from dealfinder.providers.base import HardwareProvider
from dealfinder.providers.generic import GenericJsonProvider
from dealfinder.providers.registry import (
    create_enabled_providers,
    discover_provider_plugins,
)


def test_site_alias_can_reuse_generic_provider(tmp_path: Path) -> None:
    path = tmp_path / "sites.yaml"
    path.write_text(
        """
sites:
  vendor_catalog:
    provider: generic
    enabled: true
    settings:
      endpoint: https://catalog.example.test/items
      field_map: {title: title, url: url, price: price}
"""
    )
    config = load_sites_config(path)
    providers = create_enabled_providers(config)
    assert isinstance(providers[0], GenericJsonProvider)
    assert providers[0].name == "vendor_catalog"


class PluginProvider(HardwareProvider):
    name = "external_test"

    async def search(self, criteria: SearchCriteria) -> list[HardwareListing]:
        return []


class FakeEntryPoint:
    name = "external_test"

    def load(self) -> Any:
        return PluginProvider


def test_entry_point_provider_is_discovered_without_core_changes() -> None:
    discover_provider_plugins([FakeEntryPoint()])
    providers = create_enabled_providers(
        SitesConfig(sites={"my_plugin": SiteConfig(provider="external_test")})
    )
    assert isinstance(providers[0], PluginProvider)
    assert providers[0].name == "my_plugin"


def test_site_configuration_rejects_misspelled_fields() -> None:
    with pytest.raises(ValidationError, match="extra_forbidden"):
        SiteConfig.model_validate({"enabledd": True})
