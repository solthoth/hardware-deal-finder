from datetime import UTC, datetime
from decimal import Decimal

import pytest

from dealfinder.config import SearchConfig, load_search_config
from dealfinder.models import AttributeValue, HardwareListing


@pytest.fixture
def search_config() -> SearchConfig:
    return load_search_config("config/search.yaml")


@pytest.fixture
def good_listing() -> HardwareListing:
    return HardwareListing(
        provider="fixture",
        listing_id="1",
        title="Lenovo ThinkCentre M75q Gen 2 Ryzen 5 PRO 5650GE 16GB 256GB NVMe",
        url="https://example.test/1",
        manufacturer="Lenovo",
        model="ThinkCentre M75q Gen 2",
        cpu_model="Ryzen 5 PRO 5650GE",
        cpu_vendor="AMD",
        physical_cores=AttributeValue(value=6),
        threads=AttributeValue(value=12),
        memory_gb=AttributeValue(value=16),
        max_memory_gb=AttributeValue(value=64),
        storage_gb=AttributeValue(value=256),
        storage_type="NVMe",
        ethernet_speed_gbps=AttributeValue(value=1.0),
        tpm_2=AttributeValue(value=True),
        secure_boot=AttributeValue(value=True),
        virtualization=AttributeValue(value=True),
        enterprise_features=["AMD_PRO"],
        condition="used",
        item_price=Decimal("240"),
        shipping_price=Decimal("10"),
        quantity_available=4,
        seller_rating_percent=99.7,
        seller_feedback_count=5000,
        return_policy="30 day returns",
        warranty="1 year",
        discovered_at=datetime.now(UTC),
    )
