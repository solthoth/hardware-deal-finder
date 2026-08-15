"""Provider-neutral normalization helpers for common listing text."""

from __future__ import annotations

import re
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from pydantic import HttpUrl

from dealfinder.models import AttributeValue, HardwareListing

_MEMORY = re.compile(r"\b(4|8|16|24|32|64|128)\s*GB\s*(?:RAM|MEMORY)?\b", re.IGNORECASE)
_STORAGE = re.compile(r"\b(128|256|500|512|1000|1024|2000|2048|[124])\s*(GB|TB)\b", re.IGNORECASE)
_CPU = re.compile(
    r"\b(Ryzen\s+[3579](?:\s+PRO)?\s+\d{4,5}[A-Z]{0,2}|Core\s+i[3579]-\d{4,5}[A-Z]{0,2})\b",
    re.IGNORECASE,
)


def normalize_condition(value: str | None) -> str | None:
    if not value:
        return None
    lowered = value.casefold()
    mappings = {
        "manufacturer": "manufacturer_refurbished",
        "certified": "certified_refurbished",
        "seller refurbished": "certified_refurbished",
        "excellent": "excellent_refurbished",
        "new": "new",
        "used": "used",
    }
    return next((normalized for token, normalized in mappings.items() if token in lowered), lowered)


def _capacity(match: re.Match[str] | None) -> int | None:
    if match is None:
        return None
    value = int(match.group(1))
    return value * 1000 if match.group(2).upper() == "TB" else value


def normalize_listing(provider: str, payload: dict[str, Any]) -> HardwareListing:
    """Normalize a small canonical payload used by provider adapters."""

    title = str(payload["title"])
    memory_match = _MEMORY.search(title)
    storage_matches = list(_STORAGE.finditer(title))
    storage_match = storage_matches[-1] if storage_matches else None
    cpu_match = _CPU.search(title)
    cpu_model = cpu_match.group(1) if cpu_match else None
    cpu_vendor = None
    if cpu_model:
        cpu_vendor = "AMD" if cpu_model.casefold().startswith("ryzen") else "Intel"
    memory = int(memory_match.group(1)) if memory_match else None
    storage = _capacity(storage_match)
    return HardwareListing(
        provider=provider,
        listing_id=str(payload["id"]) if payload.get("id") is not None else None,
        title=title,
        url=HttpUrl(str(payload["url"])),
        manufacturer=payload.get("manufacturer"),
        model=payload.get("model"),
        cpu_model=cpu_model,
        cpu_vendor=cpu_vendor,
        memory_gb=AttributeValue(value=memory) if memory is not None else None,
        storage_gb=AttributeValue(value=storage) if storage is not None else None,
        storage_type="NVMe" if "nvme" in title.casefold() else None,
        condition=normalize_condition(payload.get("condition")),
        item_price=Decimal(str(payload["price"])),
        shipping_price=Decimal(str(payload.get("shipping", 0))),
        currency=str(payload.get("currency", "USD")),
        quantity_available=payload.get("quantity"),
        seller_name=payload.get("seller_name"),
        seller_rating_percent=payload.get("seller_rating_percent"),
        seller_feedback_count=payload.get("seller_feedback_count"),
        return_policy=payload.get("return_policy"),
        warranty=payload.get("warranty"),
        discovered_at=payload.get("discovered_at", datetime.now(UTC)),
        raw_attributes=payload,
    )
