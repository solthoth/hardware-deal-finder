"""Hard-requirement filtering, distinct from preference scoring."""

from __future__ import annotations

from dealfinder.config import SearchCriteria
from dealfinder.models import AttributeValue, FilterDecision, HardwareListing


def _value[T](attribute: AttributeValue[T] | None) -> T | None:
    return attribute.value if attribute is not None else None


class ListingFilter:
    def __init__(self, criteria: SearchCriteria) -> None:
        self.criteria = criteria

    def evaluate(
        self, listing: HardwareListing, *, enforce_quantity: bool = True
    ) -> FilterDecision:
        reasons: list[str] = []
        warnings: list[str] = []
        self._check_basics(listing, reasons, enforce_quantity=enforce_quantity)
        self._check_specs(listing, reasons, warnings)
        self._check_security(listing, reasons, warnings)
        self._check_seller(listing, reasons, warnings)
        return FilterDecision(accepted=not reasons, reasons=reasons, warnings=warnings)

    def _check_basics(
        self,
        listing: HardwareListing,
        reasons: list[str],
        *,
        enforce_quantity: bool,
    ) -> None:
        if listing.total_price > self.criteria.price.max_per_unit:
            reasons.append(f"total price {listing.total_price} exceeds maximum")
        title = listing.title.casefold()
        for keyword in self.criteria.exclusions.keywords:
            if keyword.casefold() in title:
                reasons.append(f"excluded keyword: {keyword}")
        if (
            listing.condition
            and self.criteria.condition.allowed
            and listing.condition not in self.criteria.condition.allowed
        ):
            reasons.append(f"condition not allowed: {listing.condition}")
        if (
            enforce_quantity
            and listing.quantity_available is not None
            and listing.quantity_available < self.criteria.quantity_required
        ):
            reasons.append(
                f"quantity {listing.quantity_available} below required "
                f"{self.criteria.quantity_required}"
            )

    def _check_specs(
        self, listing: HardwareListing, reasons: list[str], warnings: list[str]
    ) -> None:
        checks: list[tuple[str, int | float | None, int | float | None]] = [
            (
                "physical cores",
                _value(listing.physical_cores),
                self.criteria.cpu.min_physical_cores,
            ),
            ("threads", _value(listing.threads), self.criteria.cpu.min_threads),
            ("memory GB", _value(listing.memory_gb), self.criteria.memory.minimum_gb),
            ("storage GB", _value(listing.storage_gb), self.criteria.storage.minimum_gb),
            (
                "network Gbps",
                _value(listing.ethernet_speed_gbps),
                self.criteria.networking.minimum_speed_gbps,
            ),
        ]
        for label, actual, minimum in checks:
            if minimum is None:
                continue
            if actual is None:
                warnings.append(f"required {label} is unknown")
            elif actual < minimum:
                reasons.append(f"{label} {actual} below minimum {minimum}")

    def _check_security(
        self, listing: HardwareListing, reasons: list[str], warnings: list[str]
    ) -> None:
        checks: list[tuple[str, bool, bool | None]] = [
            ("TPM 2.0", self.criteria.security.tpm_2_required, _value(listing.tpm_2)),
            (
                "Secure Boot",
                self.criteria.security.secure_boot_required,
                _value(listing.secure_boot),
            ),
            (
                "virtualization",
                self.criteria.security.virtualization_required,
                _value(listing.virtualization),
            ),
        ]
        for label, required, actual in checks:
            if not required:
                continue
            if actual is False:
                reasons.append(f"required {label} is not supported")
            elif actual is None:
                warnings.append(f"required {label} is unknown; verify before purchase")

    def _check_seller(
        self, listing: HardwareListing, reasons: list[str], warnings: list[str]
    ) -> None:
        checks: list[tuple[str, float | int | None, float | int | None]] = [
            (
                "seller rating",
                listing.seller_rating_percent,
                self.criteria.sellers.minimum_rating_percent,
            ),
            (
                "seller feedback",
                listing.seller_feedback_count,
                self.criteria.sellers.minimum_feedback_count,
            ),
        ]
        for label, actual, minimum in checks:
            if minimum is None:
                continue
            if actual is None:
                warnings.append(f"required {label} is unknown")
            elif actual < minimum:
                reasons.append(f"{label} {actual} below minimum {minimum}")
