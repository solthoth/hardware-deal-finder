"""Quantity-aware allocation of compatible listings into complete cluster deals."""

from __future__ import annotations

import re
from collections import defaultdict
from decimal import Decimal

from dealfinder.models import (
    AttributeValue,
    ClusterAllocation,
    ClusterDeal,
    HardwareListing,
    RankedListing,
)


def _normalized(value: str | None) -> str:
    return re.sub(r"[^a-z0-9]+", "", (value or "").casefold())


def _attribute_value[T](attribute: AttributeValue[T] | None) -> T | None:
    return attribute.value if attribute else None


def configuration_key(listing: HardwareListing) -> tuple[object, ...]:
    """Identify configurations that can reasonably be treated as identical nodes."""

    return (
        _normalized(listing.manufacturer),
        _normalized(listing.model) or _normalized(listing.title),
        _normalized(listing.cpu_model),
        _attribute_value(listing.physical_cores),
        _attribute_value(listing.threads),
        _attribute_value(listing.memory_gb),
        _attribute_value(listing.storage_gb),
        _normalized(listing.storage_type),
        _normalized(listing.condition),
    )


def _configuration_label(listing: HardwareListing) -> str:
    machine = " ".join(value for value in (listing.manufacturer, listing.model) if value)
    return machine or listing.title


def build_cluster_deals(
    ranked_listings: list[RankedListing], quantity_required: int
) -> list[ClusterDeal]:
    groups: dict[tuple[object, ...], list[RankedListing]] = defaultdict(list)
    for ranked in ranked_listings:
        if ranked.listing.quantity_available:
            groups[configuration_key(ranked.listing)].append(ranked)

    deals: list[ClusterDeal] = []
    for candidates in groups.values():
        available = sum(item.listing.quantity_available or 0 for item in candidates)
        if available < quantity_required:
            continue
        ordered = sorted(candidates, key=lambda item: item.listing.total_price)
        remaining = quantity_required
        allocations: list[ClusterAllocation] = []
        hardware_cost = Decimal(0)
        upgrade_cost = Decimal(0)
        weighted_score = 0.0
        for candidate in ordered:
            quantity = min(candidate.listing.quantity_available or 0, remaining)
            if quantity == 0:
                continue
            listing = candidate.listing
            allocations.append(
                ClusterAllocation(
                    provider=listing.provider,
                    listing_id=listing.listing_id,
                    seller_name=listing.seller_name,
                    url=listing.url,
                    quantity=quantity,
                    unit_price=listing.total_price,
                )
            )
            hardware_cost += listing.total_price * quantity
            upgrade_cost += candidate.estimated_upgrade_cost * quantity
            weighted_score += candidate.score.total * quantity
            remaining -= quantity
            if remaining == 0:
                break
        deals.append(
            ClusterDeal(
                configuration=_configuration_label(ordered[0].listing),
                quantity=quantity_required,
                allocations=allocations,
                hardware_cost=hardware_cost,
                upgrade_cost=upgrade_cost,
                score=round(weighted_score / quantity_required, 2),
                cores_per_node=_attribute_value(ordered[0].listing.physical_cores),
                threads_per_node=_attribute_value(ordered[0].listing.threads),
                installed_memory_gb_per_node=_attribute_value(ordered[0].listing.memory_gb),
            )
        )
    return sorted(deals, key=lambda deal: (-deal.score, deal.total_cost))
