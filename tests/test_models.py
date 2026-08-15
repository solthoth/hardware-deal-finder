from datetime import UTC, datetime
from decimal import Decimal

import pytest
from pydantic import ValidationError

from dealfinder.models import AttributeSource, AttributeValue, HardwareListing


def test_listing_computes_total_price_and_preserves_provenance() -> None:
    listing = HardwareListing(
        provider="fixture",
        listing_id="abc",
        title="ThinkCentre M75q",
        url="https://example.test/abc",
        physical_cores=AttributeValue(
            value=6, source=AttributeSource.CPU_DATABASE, confidence=0.99
        ),
        item_price=Decimal("240"),
        shipping_price=Decimal("12.50"),
        discovered_at=datetime.now(UTC),
    )
    assert listing.total_price == Decimal("252.50")
    assert listing.physical_cores is not None
    assert listing.physical_cores.source is AttributeSource.CPU_DATABASE


def test_money_cannot_be_negative() -> None:
    with pytest.raises(ValidationError):
        HardwareListing(
            provider="fixture",
            title="bad",
            url="https://example.test/bad",
            item_price=Decimal("-1"),
            discovered_at=datetime.now(UTC),
        )
