"""Transparent, configurable weighted deal scoring."""

from __future__ import annotations

from decimal import Decimal

from dealfinder.config import ScoringWeights, SearchCriteria, UpgradeCosts
from dealfinder.models import AttributeValue, HardwareListing, RankedListing, ScoreBreakdown


def _value[T](attribute: AttributeValue[T] | None, default: T) -> T:
    return attribute.value if attribute is not None else default


def _ratio(value: float, target: float) -> float:
    return min(100.0, max(0.0, value / target * 100)) if target else 100.0


class DealScorer:
    def __init__(
        self, criteria: SearchCriteria, weights: ScoringWeights, upgrade_costs: UpgradeCosts
    ) -> None:
        self.criteria = criteria
        self.weights = weights
        self.upgrade_costs = upgrade_costs

    def score(self, listing: HardwareListing) -> RankedListing:
        preferred_price = float(self.criteria.price.preferred_max)
        price = float(listing.total_price)
        price_score = (
            100
            if price <= preferred_price
            else _ratio(
                float(self.criteria.price.max_per_unit) - price,
                float(self.criteria.price.max_per_unit) - preferred_price,
            )
        )
        preferred_cpu = (listing.cpu_model or "").casefold() in {
            cpu.casefold() for cpu in self.criteria.cpu.preferred_models
        }
        cpu_score = (
            100.0
            if preferred_cpu
            else _ratio(
                float(_value(listing.physical_cores, 0)),
                float(self.criteria.cpu.min_physical_cores or 1),
            )
        )
        memory_score = _ratio(
            float(_value(listing.memory_gb, 0)), float(self.criteria.memory.desired_gb or 1)
        )
        if _value(listing.max_memory_gb, 0) >= (self.criteria.memory.upgradeable_to_gb or 10**9):
            memory_score = min(100, memory_score + 25)
        storage_score = _ratio(
            float(_value(listing.storage_gb, 0)), float(self.criteria.storage.desired_gb or 1)
        )
        if (
            self.criteria.storage.nvme_preferred
            and (listing.storage_type or "").casefold() == "nvme"
        ):
            storage_score = min(100, storage_score + 25)
        security_values = [
            _value(listing.tpm_2, False),
            _value(listing.secure_boot, False),
            _value(listing.virtualization, False),
            bool(listing.enterprise_features),
        ]
        security_score = sum(security_values) / len(security_values) * 100
        networking_score = _ratio(
            float(_value(listing.ethernet_speed_gbps, 0)),
            float(self.criteria.networking.preferred_speed_gbps or 1),
        )
        seller_score = listing.seller_rating_percent or 0
        warranty_score = (
            100.0
            if listing.warranty and listing.return_policy
            else (50.0 if listing.warranty or listing.return_policy else 0.0)
        )
        categories = {
            "price": price_score,
            "cpu": cpu_score,
            "memory": memory_score,
            "storage": storage_score,
            "security": security_score,
            "networking": networking_score,
            "seller": seller_score,
            "warranty": warranty_score,
        }
        total = sum(categories[name] * weight for name, weight in self.weights.model_dump().items())
        explanation = self._explain(listing, preferred_cpu)
        return RankedListing(
            listing=listing,
            score=ScoreBreakdown(
                total=round(total, 2),
                categories={name: round(value, 2) for name, value in categories.items()},
                explanation=explanation,
            ),
            estimated_upgrade_cost=self._upgrade_cost(listing),
            quantity_required=self.criteria.quantity_required,
            warnings=list(listing.raw_attributes.get("warnings", [])),
        )

    def _upgrade_cost(self, listing: HardwareListing) -> Decimal:
        total = Decimal(0)
        memory = _value(listing.memory_gb, 0)
        desired_memory = self.criteria.memory.desired_gb
        if desired_memory and memory < desired_memory:
            total += self.upgrade_costs.ram.get(desired_memory, Decimal(0))
        storage = _value(listing.storage_gb, 0)
        desired_storage = self.criteria.storage.desired_gb
        if desired_storage and storage < desired_storage:
            total += self.upgrade_costs.nvme.get(desired_storage, Decimal(0))
        return total

    def _explain(self, listing: HardwareListing, preferred_cpu: bool) -> list[str]:
        preference = "a" if preferred_cpu else "not a"
        sign = "+" if preferred_cpu else "-"
        messages = [
            f"+ Total delivered price is ${listing.total_price}",
            f"{sign} CPU is {preference} preferred model",
        ]
        if listing.quantity_available is None:
            messages.append("- Available quantity is unknown; verify before purchase")
        elif listing.quantity_available >= self.criteria.quantity_required:
            messages.append(
                f"+ Available quantity satisfies {self.criteria.quantity_required} nodes"
            )
        if _value(listing.ethernet_speed_gbps, 0) < (
            self.criteria.networking.preferred_speed_gbps or 0
        ):
            messages.append("- Networking is below the preferred speed")
        return messages
