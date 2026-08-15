"""Human- and machine-readable search renderers."""

from __future__ import annotations

import csv
import io
import json

from dealfinder.config import SearchCriteria
from dealfinder.models import AttributeValue, RankedListing
from dealfinder.service import SearchRun


def _value[T](attribute: AttributeValue[T] | None, suffix: str = "") -> str:
    return f"{attribute.value}{suffix}" if attribute else "?"


def render_table(run: SearchRun, criteria: SearchCriteria) -> str:
    lines = [
        "Hardware Deal Finder",
        f"Search: {criteria.category} | Quantity: {criteria.quantity_required} | "
        f"Maximum: ${criteria.price.max_per_unit}/node",
        "",
        f"{'Rank':<5} {'Score':<7} {'Provider':<11} {'Machine':<39} {'RAM':<7} {'Total':>9}",
        "-" * 84,
    ]
    for rank, result in enumerate(run.ranked, start=1):
        listing = result.listing
        lines.append(
            f"{rank:<5} {result.score.total:<7.1f} {listing.provider:<11} "
            f"{listing.title[:38]:<39} {_value(listing.memory_gb, 'GB'):<7} "
            f"${listing.total_price:>8}"
        )
    if not run.ranked:
        lines.append("No single listing can satisfy the requested quantity.")
    if run.cluster_deals:
        best_cluster = run.cluster_deals[0]
        lines.extend(
            [
                "",
                "Best Cluster Deal",
                f"  {best_cluster.configuration}",
                f"  Quantity: {best_cluster.quantity}",
                f"  Hardware: ${best_cluster.hardware_cost}",
                f"  Estimated upgrades: ${best_cluster.upgrade_cost}",
                f"  Estimated cluster total: ${best_cluster.total_cost}",
            ]
        )
        if best_cluster.cores_per_node and best_cluster.threads_per_node:
            lines.append(
                f"  CPU total: {best_cluster.cores_per_node * best_cluster.quantity} cores / "
                f"{best_cluster.threads_per_node * best_cluster.quantity} threads"
            )
        if best_cluster.installed_memory_gb_per_node:
            lines.append(
                f"  Installed RAM total: "
                f"{best_cluster.installed_memory_gb_per_node * best_cluster.quantity} GB"
            )
        lines.append("  Allocations:")
        lines.extend(
            f"    {allocation.quantity} x {allocation.provider} / "
            f"{allocation.seller_name or 'unknown seller'} @ ${allocation.unit_price}"
            for allocation in best_cluster.allocations
        )
    elif not run.ranked:
        lines.append("No complete cluster deal found.")
    if run.provider_results:
        lines.extend(["", "Providers:"])
        for name, provider_result in run.provider_results.items():
            detail = f" — {provider_result.message}" if provider_result.message else ""
            lines.append(
                f"  {name}: {provider_result.status.value} "
                f"({provider_result.listing_count} listings){detail}"
            )
    return "\n".join(lines)


def render_json(run: SearchRun) -> str:
    return json.dumps(run.model_dump(mode="json"), indent=2)


def render_csv(run: SearchRun) -> str:
    output = io.StringIO()
    writer = csv.writer(output, lineterminator="\n")
    writer.writerow(
        ["rank", "provider", "score", "title", "url", "price", "shipping", "total", "quantity"]
    )
    for rank, result in enumerate(run.ranked, start=1):
        listing = result.listing
        writer.writerow(
            [
                rank,
                listing.provider,
                result.score.total,
                listing.title,
                listing.url,
                listing.item_price,
                listing.shipping_price,
                listing.total_price,
                listing.quantity_available,
            ]
        )
    return output.getvalue()


def render_detail(result: RankedListing) -> str:
    listing = result.listing
    fields = {
        "URL": str(listing.url),
        "Seller": listing.seller_name or "unknown",
        "Condition": listing.condition or "unknown",
        "CPU": listing.cpu_model or "unknown",
        "Cores / threads": f"{_value(listing.physical_cores)} / {_value(listing.threads)}",
        "Memory": _value(listing.memory_gb, " GB"),
        "Maximum memory": _value(listing.max_memory_gb, " GB"),
        "Storage": f"{_value(listing.storage_gb, ' GB')} {listing.storage_type or ''}".strip(),
        "Networking": _value(listing.ethernet_speed_gbps, " Gbps"),
        "TPM 2.0": _value(listing.tpm_2),
        "Secure Boot": _value(listing.secure_boot),
        "Virtualization": _value(listing.virtualization),
        "Return policy": listing.return_policy or "unknown",
        "Warranty": listing.warranty or "unknown",
        "Delivered price": f"${listing.total_price}",
        "Estimated node upgrades": f"${result.estimated_upgrade_cost}",
        "Required quantity total": f"${result.required_quantity_cost}",
    }
    lines = [listing.title, f"Score: {result.score.total:.1f}/100", ""]
    lines.extend(f"{label}: {value}" for label, value in fields.items())
    lines.extend(["", "Score breakdown:"])
    lines.extend(f"  {name}: {score:.1f}" for name, score in result.score.categories.items())
    lines.extend(["", "Why this rank:", *result.score.explanation])
    if listing.attribute_provenance:
        lines.extend(["", "Attribute provenance:"])
        for attribute, evidence in sorted(listing.attribute_provenance.items()):
            reference = f" ({evidence.reference})" if evidence.reference else ""
            lines.append(
                f"- {attribute}: {evidence.source.value}, "
                f"confidence {evidence.confidence:.2f}{reference}"
            )
    missing = [label for label, value in fields.items() if value in {"unknown", "?"}]
    if missing:
        lines.extend(["", "Missing information:", *(f"- {label}" for label in missing)])
    if result.warnings:
        lines.extend(["", "Warnings:", *(f"- {warning}" for warning in result.warnings)])
    return "\n".join(lines)
