from decimal import Decimal

from dealfinder.config import load_search_config
from dealfinder.models import HardwareListing
from dealfinder.scoring import DealScorer
from dealfinder.service import SearchRun
from dealfinder.watch import DealEventType, detect_deal_events


def test_watch_detects_new_strong_deal(good_listing: HardwareListing) -> None:
    config = load_search_config("config/search.yaml")
    ranked = DealScorer(config.search, config.scoring, config.upgrade_costs).score(good_listing)
    events = detect_deal_events(
        SearchRun(ranked=[ranked], provider_results={}),
        previous=None,
        minimum_score=80,
        minimum_price_drop_percent=5,
    )
    assert [event.event_type for event in events] == [DealEventType.NEW_STRONG_DEAL]


def test_watch_detects_material_price_drop(good_listing: HardwareListing) -> None:
    config = load_search_config("config/search.yaml")
    scorer = DealScorer(config.search, config.scoring, config.upgrade_costs)
    previous = scorer.score(good_listing)
    cheaper_listing = good_listing.model_copy(update={"item_price": Decimal("200")})
    current = scorer.score(cheaper_listing)
    events = detect_deal_events(
        SearchRun(ranked=[current], provider_results={}),
        SearchRun(ranked=[previous], provider_results={}),
        minimum_score=101,
        minimum_price_drop_percent=10,
    )
    assert len(events) == 1
    assert events[0].event_type is DealEventType.PRICE_DROP
    assert events[0].price_drop_percent == Decimal("16.00")
