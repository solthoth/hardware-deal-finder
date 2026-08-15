from decimal import Decimal

from dealfinder.enrichment import KnowledgeEnricher
from dealfinder.models import AttributeSource, HardwareListing


def test_machine_enrichment_uses_audited_manufacturer_facts() -> None:
    listing = HardwareListing(
        provider="fixture",
        title="Lenovo ThinkCentre M75q Gen 2 Ryzen 5 PRO 5650GE 16GB 512GB NVMe",
        url="https://example.test/lenovo",
        cpu_model="Ryzen 5 PRO 5650GE",
        item_price=Decimal("250"),
    )
    enriched = KnowledgeEnricher().enrich(listing)
    assert enriched.manufacturer == "Lenovo"
    assert enriched.model == "ThinkCentre M75q Gen 2"
    assert enriched.max_memory_gb is not None
    assert enriched.max_memory_gb.value == 64
    assert enriched.max_memory_gb.source is AttributeSource.MANUFACTURER_SPEC
    assert enriched.attribute_provenance["model"].source is AttributeSource.INFERRED
    assert str(enriched.attribute_provenance["max_memory_gb"].reference).startswith(
        "https://psref.lenovo.com/"
    )
    assert (
        enriched.attribute_provenance["enterprise_features.AMD_PRO"].source
        is AttributeSource.CPU_DATABASE
    )


def test_dell_machine_enrichment_tracks_security_source() -> None:
    listing = HardwareListing(
        provider="fixture",
        title="Dell OptiPlex 7090 Micro Core i5-11500T 16GB 512GB NVMe",
        url="https://example.test/dell",
        cpu_model="Core i5-11500T",
        item_price=Decimal("260"),
    )
    enriched = KnowledgeEnricher().enrich(listing)
    assert enriched.tpm_2 is not None and enriched.tpm_2.value is True
    assert enriched.secure_boot is not None and enriched.secure_boot.value is True
    assert enriched.tpm_2.source is AttributeSource.MANUFACTURER_SPEC
    assert "tpm_2" in enriched.attribute_provenance


def test_unknown_machine_does_not_receive_manufacturer_facts() -> None:
    listing = HardwareListing(
        provider="fixture",
        title="Unknown Tiny Computer 16GB",
        url="https://example.test/unknown",
        item_price=Decimal("100"),
    )
    enriched = KnowledgeEnricher().enrich(listing)
    assert enriched.manufacturer is None
    assert enriched.max_memory_gb is None
    assert enriched.attribute_provenance == {}
