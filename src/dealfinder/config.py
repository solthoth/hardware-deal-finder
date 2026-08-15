"""Validated YAML configuration models and loaders."""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, ConfigDict, Field, model_validator


class ConfigModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class PriceCriteria(ConfigModel):
    max_per_unit: Decimal = Field(gt=0)
    preferred_max: Decimal = Field(gt=0)


class CpuCriteria(ConfigModel):
    vendors: list[str] = Field(default_factory=list)
    min_physical_cores: int | None = Field(default=None, gt=0)
    min_threads: int | None = Field(default=None, gt=0)
    preferred_models: list[str] = Field(default_factory=list)


class MemoryCriteria(ConfigModel):
    minimum_gb: int | None = Field(default=None, gt=0)
    desired_gb: int | None = Field(default=None, gt=0)
    upgradeable_to_gb: int | None = Field(default=None, gt=0)


class StorageCriteria(ConfigModel):
    minimum_gb: int | None = Field(default=None, gt=0)
    desired_gb: int | None = Field(default=None, gt=0)
    nvme_preferred: bool = False


class NetworkingCriteria(ConfigModel):
    minimum_speed_gbps: float | None = Field(default=None, gt=0)
    preferred_speed_gbps: float | None = Field(default=None, gt=0)


class SecurityCriteria(ConfigModel):
    tpm_2_required: bool = False
    secure_boot_required: bool = False
    virtualization_required: bool = False
    iommu_preferred: bool = False


class EnterpriseCriteria(ConfigModel):
    preferred: bool = False
    capabilities: list[str] = Field(default_factory=list)


class ConditionCriteria(ConfigModel):
    allowed: list[str] = Field(default_factory=list)


class SellerCriteria(ConfigModel):
    minimum_rating_percent: float | None = Field(default=None, ge=0, le=100)
    minimum_feedback_count: int | None = Field(default=None, ge=0)


class ExclusionCriteria(ConfigModel):
    keywords: list[str] = Field(default_factory=list)


class SearchCriteria(ConfigModel):
    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    category: str
    query: str | None = None
    quantity_required: int = Field(default=1, gt=0)
    price: PriceCriteria
    cpu: CpuCriteria = Field(default_factory=CpuCriteria)
    memory: MemoryCriteria = Field(default_factory=MemoryCriteria)
    storage: StorageCriteria = Field(default_factory=StorageCriteria)
    networking: NetworkingCriteria = Field(default_factory=NetworkingCriteria)
    security: SecurityCriteria = Field(default_factory=SecurityCriteria)
    enterprise: EnterpriseCriteria = Field(default_factory=EnterpriseCriteria)
    condition: ConditionCriteria = Field(default_factory=ConditionCriteria)
    sellers: SellerCriteria = Field(default_factory=SellerCriteria)
    exclusions: ExclusionCriteria = Field(default_factory=ExclusionCriteria)


class ScoringWeights(ConfigModel):
    price: float = 0.30
    cpu: float = 0.20
    memory: float = 0.15
    storage: float = 0.10
    security: float = 0.10
    networking: float = 0.05
    seller: float = 0.05
    warranty: float = 0.05

    @model_validator(mode="after")
    def weights_total_one(self) -> ScoringWeights:
        if abs(sum(self.model_dump().values()) - 1.0) > 1e-6:
            raise ValueError("scoring weights must sum to 1.0")
        return self


def _normalize_upgrade_map(values: dict[str | int, Decimal]) -> dict[int, Decimal]:
    return {int(str(key).removesuffix("_gb")): value for key, value in values.items()}


class UpgradeCosts(ConfigModel):
    ram: dict[int, Decimal] = Field(default_factory=dict)
    nvme: dict[int, Decimal] = Field(default_factory=dict)

    @model_validator(mode="before")
    @classmethod
    def normalize_keys(cls, data: Any) -> Any:
        if not isinstance(data, dict):
            return data
        return {
            **data,
            "ram": _normalize_upgrade_map(data.get("ram", {})),
            "nvme": _normalize_upgrade_map(data.get("nvme", {})),
        }


class WatchConfig(ConfigModel):
    minimum_score: float = Field(default=85, ge=0, le=100)
    minimum_price_drop_percent: Decimal = Field(default=Decimal("5"), gt=0, le=100)


class SearchConfig(ConfigModel):
    search: SearchCriteria
    scoring: ScoringWeights = Field(default_factory=ScoringWeights)
    upgrade_costs: UpgradeCosts = Field(default_factory=UpgradeCosts)
    watch: WatchConfig = Field(default_factory=WatchConfig)


class SiteDefaults(ConfigModel):
    request_timeout_seconds: float = Field(default=15, gt=0)
    rate_limit_per_second: float = Field(default=1, gt=0)
    max_listings: int = Field(default=50, gt=0)


class SiteConfig(ConfigModel):
    name: str | None = None
    provider: str | None = None
    enabled: bool = True
    trust_weight: float = Field(default=1, ge=0, le=1)
    request_timeout_seconds: float = Field(default=15, gt=0)
    rate_limit_per_second: float = Field(default=1, gt=0)
    max_listings: int = Field(default=50, gt=0)
    settings: dict[str, Any] = Field(default_factory=dict)


class SitesConfig(ConfigModel):
    defaults: SiteDefaults = Field(default_factory=SiteDefaults)
    sites: dict[str, SiteConfig]


def _read_yaml(path: str | Path) -> dict[str, Any]:
    with Path(path).open(encoding="utf-8") as stream:
        value = yaml.safe_load(stream) or {}
    if not isinstance(value, dict):
        raise ValueError(f"configuration root must be a mapping: {path}")
    return value


def load_search_config(path: str | Path) -> SearchConfig:
    return SearchConfig.model_validate(_read_yaml(path))


def load_sites_config(path: str | Path) -> SitesConfig:
    data = _read_yaml(path)
    defaults = SiteDefaults.model_validate(data.get("defaults", {}))
    default_values = defaults.model_dump()
    data["sites"] = {
        name: {**default_values, "name": name, **settings}
        for name, settings in data.get("sites", {}).items()
    }
    return SitesConfig.model_validate(data)
