from decimal import Decimal

import pytest

from dealfinder.cluster import build_cluster_deals
from dealfinder.config import SearchConfig, SiteConfig
from dealfinder.models import HardwareListing
from dealfinder.providers.fixture import FixtureProvider
from dealfinder.reporting import render_table
from dealfinder.scoring import DealScorer
from dealfinder.service import SearchService


def test_cluster_plan_combines_compatible_partial_listings(
    search_config: SearchConfig, good_listing: HardwareListing
) -> None:
    first = good_listing.model_copy(
        update={
            "listing_id": "seller-a",
            "seller_name": "seller-a",
            "quantity_available": 2,
        }
    )
    second = good_listing.model_copy(
        update={
            "listing_id": "seller-b",
            "seller_name": "seller-b",
            "quantity_available": 1,
            "item_price": Decimal("220"),
        }
    )
    scorer = DealScorer(search_config.search, search_config.scoring, search_config.upgrade_costs)
    plans = build_cluster_deals(
        [scorer.score(first), scorer.score(second)], search_config.search.quantity_required
    )
    assert len(plans) == 1
    assert [(item.listing_id, item.quantity) for item in plans[0].allocations] == [
        ("seller-b", 1),
        ("seller-a", 2),
    ]
    assert plans[0].hardware_cost == Decimal("730")
    assert plans[0].upgrade_cost == Decimal("330")
    assert plans[0].total_cost == Decimal("1060")


def test_cluster_plan_does_not_mix_different_configurations(
    search_config: SearchConfig, good_listing: HardwareListing
) -> None:
    different_memory = good_listing.model_copy(
        update={
            "listing_id": "other",
            "quantity_available": 2,
            "memory_gb": good_listing.memory_gb.model_copy(update={"value": 32}),
        }
    )
    one_unit = good_listing.model_copy(update={"quantity_available": 1})
    scorer = DealScorer(search_config.search, search_config.scoring, search_config.upgrade_costs)
    assert build_cluster_deals([scorer.score(one_unit), scorer.score(different_memory)], 3) == []


@pytest.mark.asyncio
async def test_service_distinguishes_individual_and_grouped_cluster_deals(
    search_config: SearchConfig, good_listing: HardwareListing
) -> None:
    listings = [
        good_listing.model_copy(
            update={"listing_id": "a", "seller_name": "a", "quantity_available": 2}
        ),
        good_listing.model_copy(
            update={"listing_id": "b", "seller_name": "b", "quantity_available": 1}
        ),
    ]
    provider = FixtureProvider(SiteConfig(), listings=listings)
    run = await SearchService.from_config(search_config, [provider]).search()
    assert run.ranked == []
    assert len(run.cluster_deals) == 1
    assert run.cluster_deals[0].quantity == 3
    output = render_table(run, search_config.search)
    assert "Best Cluster Deal" in output
    assert "1 x fixture / b" in output
