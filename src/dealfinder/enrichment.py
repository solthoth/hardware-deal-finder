"""Conservative enrichment from a small, auditable hardware knowledge base."""

from __future__ import annotations

import re
from dataclasses import dataclass

from pydantic import HttpUrl

from dealfinder.models import (
    AttributeEvidence,
    AttributeSource,
    AttributeValue,
    HardwareListing,
)


@dataclass(frozen=True)
class CpuFacts:
    cores: int
    threads: int
    enterprise_features: tuple[str, ...]


@dataclass(frozen=True)
class MachineFacts:
    pattern: re.Pattern[str]
    manufacturer: str
    model: str
    max_memory_gb: int
    reference: HttpUrl
    tpm_2: bool | None = None
    secure_boot: bool | None = None
    security_reference: HttpUrl | None = None


CPU_FACTS: dict[str, CpuFacts] = {
    "ryzen 5 pro 5650ge": CpuFacts(6, 12, ("AMD_PRO",)),
    "ryzen 5 pro 5750ge": CpuFacts(8, 16, ("AMD_PRO",)),
    "ryzen 7 pro 4750ge": CpuFacts(8, 16, ("AMD_PRO",)),
    "ryzen 7 pro 5750ge": CpuFacts(8, 16, ("AMD_PRO",)),
    "core i5-10500t": CpuFacts(6, 12, ("Intel_vPro", "Intel_AMT")),
    "core i5-11500t": CpuFacts(6, 12, ("Intel_vPro", "Intel_AMT")),
    "core i5-12500t": CpuFacts(6, 12, ("Intel_vPro", "Intel_AMT")),
}

MACHINE_FACTS: tuple[MachineFacts, ...] = (
    MachineFacts(
        re.compile(r"\b(?:thinkcentre\s+)?m75q\s+gen\s*2\b", re.IGNORECASE),
        "Lenovo",
        "ThinkCentre M75q Gen 2",
        64,
        HttpUrl(
            "https://psref.lenovo.com/syspool/Sys/PDF/ThinkCentre/"
            "ThinkCentre_M75q_Gen_2/ThinkCentre_M75q_Gen_2_Spec.pdf"
        ),
    ),
    MachineFacts(
        re.compile(r"\b(?:thinkcentre\s+)?m90q\s+gen\s*2\b", re.IGNORECASE),
        "Lenovo",
        "ThinkCentre M90q Gen 2",
        64,
        HttpUrl(
            "https://psref.lenovo.com/syspool/Sys/PDF/ThinkCentre/"
            "ThinkCentre_M90q_Gen_2/ThinkCentre_M90q_Gen_2_Spec.pdf"
        ),
    ),
    MachineFacts(
        re.compile(r"\b(?:thinkcentre\s+)?m70q\s+gen\s*2\b", re.IGNORECASE),
        "Lenovo",
        "ThinkCentre M70q Gen 2",
        64,
        HttpUrl(
            "https://psref.lenovo.com/syspool/Sys/PDF/ThinkCentre/"
            "ThinkCentre_M70q_Gen_2/ThinkCentre_M70q_Gen_2_Spec.pdf"
        ),
    ),
    MachineFacts(
        re.compile(r"\b(?:dell\s+)?optiplex\s+7090\s+(?:micro|mff)\b", re.IGNORECASE),
        "Dell",
        "OptiPlex 7090 Micro",
        64,
        HttpUrl(
            "https://www.dell.com/support/manuals/en-us/optiplex-7090-micro/"
            "opti7090mff_setupspecs/memory"
        ),
        tpm_2=True,
        secure_boot=True,
        security_reference=HttpUrl(
            "https://www.dell.com/support/manuals/en-us/optiplex-7090-micro/"
            "opti7090mff_setupspecs/hardware-security"
        ),
    ),
    MachineFacts(
        re.compile(r"\b(?:dell\s+)?optiplex\s+7000\s+(?:micro|mff)\b", re.IGNORECASE),
        "Dell",
        "OptiPlex 7000 Micro",
        64,
        HttpUrl(
            "https://www.dell.com/support/manuals/en-us/oth-7000xe-micro/"
            "optiplex_7000_mff_setup_specs/memory"
        ),
    ),
)


class KnowledgeEnricher:
    def enrich(self, listing: HardwareListing) -> HardwareListing:
        enriched = self._enrich_machine(listing)
        return self._enrich_cpu(enriched)

    def _enrich_machine(self, listing: HardwareListing) -> HardwareListing:
        facts = next(
            (candidate for candidate in MACHINE_FACTS if candidate.pattern.search(listing.title)),
            None,
        )
        if facts is None:
            return listing
        updates: dict[str, object] = {}
        provenance = dict(listing.attribute_provenance)
        inferred = AttributeEvidence(
            source=AttributeSource.INFERRED,
            confidence=0.98,
            reference=facts.reference,
        )
        manufacturer_spec = AttributeEvidence(
            source=AttributeSource.MANUFACTURER_SPEC,
            confidence=1.0,
            reference=facts.reference,
        )
        if listing.manufacturer is None:
            updates["manufacturer"] = facts.manufacturer
            provenance["manufacturer"] = inferred
        if listing.model is None:
            updates["model"] = facts.model
            provenance["model"] = inferred
        if listing.max_memory_gb is None:
            updates["max_memory_gb"] = AttributeValue(
                value=facts.max_memory_gb,
                source=AttributeSource.MANUFACTURER_SPEC,
                confidence=1.0,
            )
            provenance["max_memory_gb"] = manufacturer_spec
        security_evidence = AttributeEvidence(
            source=AttributeSource.MANUFACTURER_SPEC,
            confidence=1.0,
            reference=facts.security_reference or facts.reference,
        )
        if listing.tpm_2 is None and facts.tpm_2 is not None:
            updates["tpm_2"] = AttributeValue(
                value=facts.tpm_2,
                source=AttributeSource.MANUFACTURER_SPEC,
                confidence=1.0,
            )
            provenance["tpm_2"] = security_evidence
        if listing.secure_boot is None and facts.secure_boot is not None:
            updates["secure_boot"] = AttributeValue(
                value=facts.secure_boot,
                source=AttributeSource.MANUFACTURER_SPEC,
                confidence=1.0,
            )
            provenance["secure_boot"] = security_evidence
        updates["attribute_provenance"] = provenance
        return listing.model_copy(update=updates)

    def _enrich_cpu(self, listing: HardwareListing) -> HardwareListing:
        cpu_name = (listing.cpu_model or "").casefold()
        facts = CPU_FACTS.get(cpu_name)
        if facts is None:
            return listing
        updates: dict[str, object] = {}
        provenance = dict(listing.attribute_provenance)
        cpu_evidence = AttributeEvidence(source=AttributeSource.CPU_DATABASE, confidence=0.99)
        if listing.physical_cores is None:
            updates["physical_cores"] = AttributeValue(
                value=facts.cores, source=AttributeSource.CPU_DATABASE, confidence=0.99
            )
            provenance["physical_cores"] = cpu_evidence
        if listing.threads is None:
            updates["threads"] = AttributeValue(
                value=facts.threads, source=AttributeSource.CPU_DATABASE, confidence=0.99
            )
            provenance["threads"] = cpu_evidence
        if listing.virtualization is None:
            updates["virtualization"] = AttributeValue(
                value=True, source=AttributeSource.CPU_DATABASE, confidence=0.99
            )
            provenance["virtualization"] = cpu_evidence
        updates["enterprise_features"] = sorted(
            set(listing.enterprise_features).union(facts.enterprise_features)
        )
        for feature in facts.enterprise_features:
            if feature not in listing.enterprise_features:
                provenance[f"enterprise_features.{feature}"] = cpu_evidence
        updates["attribute_provenance"] = provenance
        return listing.model_copy(update=updates)
