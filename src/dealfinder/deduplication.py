"""Deterministic exact-semantic deduplication for normalized listings."""

from __future__ import annotations

import re

from dealfinder.models import HardwareListing


def _normalized(value: str | None) -> str:
    return re.sub(r"[^a-z0-9]+", "", (value or "").casefold())


def listing_fingerprint(listing: HardwareListing) -> tuple[object, ...]:
    return (
        _normalized(listing.manufacturer),
        _normalized(listing.model),
        _normalized(listing.cpu_model),
        listing.memory_gb.value if listing.memory_gb else None,
        listing.storage_gb.value if listing.storage_gb else None,
        _normalized(listing.seller_name),
        listing.total_price,
    )


def deduplicate(listings: list[HardwareListing]) -> list[HardwareListing]:
    seen: set[tuple[object, ...]] = set()
    unique: list[HardwareListing] = []
    for listing in listings:
        fingerprint = listing_fingerprint(listing)
        if fingerprint in seen:
            continue
        seen.add(fingerprint)
        unique.append(listing)
    return unique
