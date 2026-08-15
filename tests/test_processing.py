from decimal import Decimal

from dealfinder.config import SearchConfig
from dealfinder.deduplication import deduplicate
from dealfinder.enrichment import KnowledgeEnricher
from dealfinder.filtering import ListingFilter
from dealfinder.models import HardwareListing
from dealfinder.normalization import normalize_condition, normalize_listing
from dealfinder.scoring import DealScorer


def test_normalization_extracts_common_listing_attributes() -> None:
    listing = normalize_listing(
        provider="fixture",
        payload={
            "id": "x",
            "title": "HP EliteDesk Ryzen 5 PRO 5650GE 16 GB RAM 1 TB NVMe",
            "url": "https://example.test/x",
            "price": "249.99",
            "shipping": "0",
            "condition": "Seller refurbished",
        },
    )
    assert listing.memory_gb is not None and listing.memory_gb.value == 16
    assert listing.storage_gb is not None and listing.storage_gb.value == 1000
    assert listing.storage_type == "NVMe"
    assert normalize_condition("Seller refurbished") == "certified_refurbished"


def test_enrichment_adds_only_known_values_with_provenance() -> None:
    listing = normalize_listing(
        provider="fixture",
        payload={
            "title": "Lenovo M75q Gen 2 Ryzen 5 PRO 5650GE 16GB 256GB NVMe",
            "url": "https://example.test/x",
            "price": "250",
        },
    )
    enriched = KnowledgeEnricher().enrich(listing)
    assert enriched.physical_cores is not None and enriched.physical_cores.value == 6
    assert enriched.physical_cores.source.value == "cpu_database"
    assert enriched.virtualization is not None and enriched.virtualization.value is True
    assert "AMD_PRO" in enriched.enterprise_features


def test_filter_enforces_price_quantity_and_exclusions(
    search_config: SearchConfig, good_listing: HardwareListing
) -> None:
    listing = good_listing.model_copy(
        update={"title": "Broken parts only", "quantity_available": 1}
    )
    decision = ListingFilter(search_config.search).evaluate(listing)
    assert not decision.accepted
    assert any("excluded keyword" in reason for reason in decision.reasons)
    assert any("quantity" in reason for reason in decision.reasons)


def test_filter_reports_unknown_required_security_as_warning(
    search_config: SearchConfig, good_listing: HardwareListing
) -> None:
    listing = good_listing.model_copy(update={"tpm_2": None})
    decision = ListingFilter(search_config.search).evaluate(listing)
    assert decision.accepted
    assert any("TPM 2.0 is unknown" in warning for warning in decision.warnings)


def test_scoring_is_transparent_quantity_and_upgrade_aware(
    search_config: SearchConfig, good_listing: HardwareListing
) -> None:
    ranked = DealScorer(
        search_config.search, search_config.scoring, search_config.upgrade_costs
    ).score(good_listing)
    assert 80 <= ranked.score.total <= 100
    assert set(ranked.score.categories) == set(search_config.scoring.model_dump())
    assert ranked.estimated_upgrade_cost == Decimal("110")
    assert ranked.required_quantity_cost == Decimal("1080")
    assert any("quantity" in message.lower() for message in ranked.score.explanation)


def test_deduplication_keeps_meaningful_seller_or_price_difference(
    good_listing: HardwareListing,
) -> None:
    exact_duplicate = good_listing.model_copy()
    other_seller = good_listing.model_copy(update={"seller_name": "another"})
    price_difference = good_listing.model_copy(update={"item_price": Decimal("210")})
    assert len(deduplicate([good_listing, exact_duplicate, other_seller, price_difference])) == 3
