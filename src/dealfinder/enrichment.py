"""Conservative enrichment from a small, auditable hardware knowledge base."""

from __future__ import annotations

from dataclasses import dataclass

from dealfinder.models import AttributeSource, AttributeValue, HardwareListing


@dataclass(frozen=True)
class CpuFacts:
    cores: int
    threads: int
    enterprise_features: tuple[str, ...]


CPU_FACTS: dict[str, CpuFacts] = {
    "ryzen 5 pro 5650ge": CpuFacts(6, 12, ("AMD_PRO",)),
    "ryzen 5 pro 5750ge": CpuFacts(8, 16, ("AMD_PRO",)),
    "ryzen 7 pro 4750ge": CpuFacts(8, 16, ("AMD_PRO",)),
    "ryzen 7 pro 5750ge": CpuFacts(8, 16, ("AMD_PRO",)),
    "core i5-10500t": CpuFacts(6, 12, ("Intel_vPro", "Intel_AMT")),
    "core i5-11500t": CpuFacts(6, 12, ("Intel_vPro", "Intel_AMT")),
    "core i5-12500t": CpuFacts(6, 12, ("Intel_vPro", "Intel_AMT")),
}


class KnowledgeEnricher:
    def enrich(self, listing: HardwareListing) -> HardwareListing:
        cpu_name = (listing.cpu_model or "").casefold()
        facts = CPU_FACTS.get(cpu_name)
        if facts is None:
            return listing
        updates: dict[str, object] = {}
        if listing.physical_cores is None:
            updates["physical_cores"] = AttributeValue(
                value=facts.cores, source=AttributeSource.CPU_DATABASE, confidence=0.99
            )
        if listing.threads is None:
            updates["threads"] = AttributeValue(
                value=facts.threads, source=AttributeSource.CPU_DATABASE, confidence=0.99
            )
        if listing.virtualization is None:
            updates["virtualization"] = AttributeValue(
                value=True, source=AttributeSource.CPU_DATABASE, confidence=0.99
            )
        updates["enterprise_features"] = sorted(
            set(listing.enterprise_features).union(facts.enterprise_features)
        )
        return listing.model_copy(update=updates)
