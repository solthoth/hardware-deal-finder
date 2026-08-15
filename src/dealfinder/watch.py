"""Compare persisted search snapshots and emit actionable deal events."""

from __future__ import annotations

from decimal import Decimal
from enum import StrEnum

from pydantic import BaseModel, Field, HttpUrl

from dealfinder.models import RankedListing
from dealfinder.service import SearchRun


class DealEventType(StrEnum):
    NEW_STRONG_DEAL = "new_strong_deal"
    PRICE_DROP = "price_drop"


class DealEvent(BaseModel):
    event_type: DealEventType
    provider: str
    listing_id: str | None
    title: str
    url: HttpUrl
    current_price: Decimal = Field(ge=0)
    previous_price: Decimal | None = Field(default=None, ge=0)
    price_drop_percent: Decimal | None = Field(default=None, ge=0)
    score: float = Field(ge=0, le=100)


def _key(ranked: RankedListing) -> tuple[str, str]:
    listing = ranked.listing
    return listing.provider, listing.listing_id or str(listing.url)


def detect_deal_events(
    current: SearchRun,
    previous: SearchRun | None,
    *,
    minimum_score: float,
    minimum_price_drop_percent: Decimal | int | float,
) -> list[DealEvent]:
    previous_by_key = {_key(item): item for item in previous.ranked} if previous else {}
    threshold = Decimal(str(minimum_price_drop_percent))
    events: list[DealEvent] = []
    for ranked in current.ranked:
        listing = ranked.listing
        old = previous_by_key.get(_key(ranked))
        if old is None and ranked.score.total >= minimum_score:
            events.append(
                DealEvent(
                    event_type=DealEventType.NEW_STRONG_DEAL,
                    provider=listing.provider,
                    listing_id=listing.listing_id,
                    title=listing.title,
                    url=listing.url,
                    current_price=listing.total_price,
                    score=ranked.score.total,
                )
            )
            continue
        if old is None or old.listing.total_price <= listing.total_price:
            continue
        drop = (
            (old.listing.total_price - listing.total_price) / old.listing.total_price * Decimal(100)
        ).quantize(Decimal("0.01"))
        if drop < threshold:
            continue
        events.append(
            DealEvent(
                event_type=DealEventType.PRICE_DROP,
                provider=listing.provider,
                listing_id=listing.listing_id,
                title=listing.title,
                url=listing.url,
                current_price=listing.total_price,
                previous_price=old.listing.total_price,
                price_drop_percent=drop,
                score=ranked.score.total,
            )
        )
    return events
