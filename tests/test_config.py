from decimal import Decimal
from pathlib import Path

from dealfinder.config import load_search_config, load_sites_config


def test_load_search_config_and_cli_independent_values(tmp_path: Path) -> None:
    path = tmp_path / "search.yaml"
    path.write_text(
        """
search:
  category: mini_pc
  quantity_required: 3
  price: {max_per_unit: 350, preferred_max: 275}
  cpu: {vendors: [AMD, Intel], min_physical_cores: 6, min_threads: 12}
  memory: {minimum_gb: 16, desired_gb: 32, upgradeable_to_gb: 64}
  storage: {minimum_gb: 256, desired_gb: 1000, nvme_preferred: true}
  networking: {minimum_speed_gbps: 1, preferred_speed_gbps: 2.5}
  security: {tpm_2_required: true, secure_boot_required: true, virtualization_required: true}
  condition: {allowed: [used, new]}
  sellers: {minimum_rating_percent: 98, minimum_feedback_count: 100}
  exclusions: {keywords: [broken]}
scoring:
  {price: .3, cpu: .2, memory: .15, storage: .1, security: .1,
   networking: .05, seller: .05, warranty: .05}
upgrade_costs:
  ram: {64_gb: 95}
  nvme: {1000_gb: 65}
"""
    )
    config = load_search_config(path)
    assert config.search.quantity_required == 3
    assert config.search.price.max_per_unit == Decimal("350")
    assert config.upgrade_costs.ram[64] == Decimal("95")
    assert sum(config.scoring.model_dump().values()) == 1


def test_load_provider_specific_site_settings(tmp_path: Path) -> None:
    path = tmp_path / "sites.yaml"
    path.write_text(
        """
defaults: {request_timeout_seconds: 12, rate_limit_per_second: 2, max_listings: 40}
sites:
  ebay:
    enabled: true
    trust_weight: 0.95
    settings: {marketplace_id: EBAY_US}
"""
    )
    config = load_sites_config(path)
    assert config.sites["ebay"].request_timeout_seconds == 12
    assert config.sites["ebay"].settings["marketplace_id"] == "EBAY_US"
