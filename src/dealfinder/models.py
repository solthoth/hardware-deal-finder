"""Normalized domain models shared by every provider."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, computed_field


class AttributeSource(StrEnum):
    LISTING = "listing"
    MANUFACTURER_SPEC = "manufacturer_spec"
    CPU_DATABASE = "cpu_database"
    INFERRED = "inferred"


class AttributeValue[T](BaseModel):
    """A value plus evidence describing where it came from."""

    value: T
    source: AttributeSource = AttributeSource.LISTING
    confidence: float = Field(default=1.0, ge=0, le=1)


class HardwareListing(BaseModel):
    """Marketplace-neutral hardware listing."""

    model_config = ConfigDict(validate_assignment=True)

    provider: str
    listing_id: str | None = None
    title: str
    url: HttpUrl
    manufacturer: str | None = None
    model: str | None = None
    cpu_model: str | None = None
    cpu_vendor: str | None = None
    cpu_generation: str | None = None
    physical_cores: AttributeValue[int] | None = None
    threads: AttributeValue[int] | None = None
    memory_gb: AttributeValue[int] | None = None
    max_memory_gb: AttributeValue[int] | None = None
    storage_gb: AttributeValue[int] | None = None
    storage_type: str | None = None
    ethernet_speed_gbps: AttributeValue[float] | None = None
    ethernet_port_count: int | None = None
    tpm_2: AttributeValue[bool] | None = None
    secure_boot: AttributeValue[bool] | None = None
    virtualization: AttributeValue[bool] | None = None
    iommu: AttributeValue[bool] | None = None
    enterprise_features: list[str] = Field(default_factory=list)
    condition: str | None = None
    item_price: Decimal = Field(ge=0)
    shipping_price: Decimal = Field(default=Decimal(0), ge=0)
    currency: str = "USD"
    quantity_available: int | None = Field(default=None, ge=0)
    seller_name: str | None = None
    seller_rating_percent: float | None = Field(default=None, ge=0, le=100)
    seller_feedback_count: int | None = Field(default=None, ge=0)
    return_policy: str | None = None
    warranty: str | None = None
    discovered_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    raw_attributes: dict[str, Any] = Field(default_factory=dict, exclude=True)

    @computed_field  # type: ignore[prop-decorator]
    @property
    def total_price(self) -> Decimal:
        return self.item_price + self.shipping_price


class FilterDecision(BaseModel):
    accepted: bool
    reasons: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class ScoreBreakdown(BaseModel):
    total: float = Field(ge=0, le=100)
    categories: dict[str, float]
    explanation: list[str]


class RankedListing(BaseModel):
    listing: HardwareListing
    score: ScoreBreakdown
    estimated_upgrade_cost: Decimal = Decimal(0)
    quantity_required: int = Field(default=1, gt=0)

    @computed_field  # type: ignore[prop-decorator]
    @property
    def required_quantity_cost(self) -> Decimal:
        return (self.listing.total_price + self.estimated_upgrade_cost) * self.quantity_required
