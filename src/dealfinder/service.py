"""Failure-isolated orchestration of independent providers and deal processing."""

from __future__ import annotations

import asyncio
import logging
from enum import StrEnum
from typing import Protocol

from pydantic import BaseModel, Field

from dealfinder.cluster import build_cluster_deals
from dealfinder.config import SearchConfig
from dealfinder.deduplication import deduplicate
from dealfinder.enrichment import KnowledgeEnricher
from dealfinder.filtering import ListingFilter
from dealfinder.models import ClusterDeal, HardwareListing, RankedListing
from dealfinder.providers.base import (
    HardwareProvider,
    ProviderRateLimited,
    ProviderUnavailable,
    ProviderUnsupported,
)
from dealfinder.scoring import DealScorer

logger = logging.getLogger(__name__)


class ProviderStatus(StrEnum):
    AVAILABLE = "available"
    UNAVAILABLE = "unavailable"
    RATE_LIMITED = "rate_limited"
    ERROR = "error"
    UNSUPPORTED = "unsupported"


class ProviderResult(BaseModel):
    status: ProviderStatus
    listing_count: int = 0
    message: str | None = None


class SearchRun(BaseModel):
    ranked: list[RankedListing]
    cluster_deals: list[ClusterDeal] = Field(default_factory=list)
    provider_results: dict[str, ProviderResult]
    rejected_count: int = 0
    run_id: int | None = None


class ResultStore(Protocol):
    def save(self, ranked: list[RankedListing]) -> int: ...


class SearchService:
    def __init__(
        self,
        config: SearchConfig,
        providers: list[HardwareProvider],
        *,
        enricher: KnowledgeEnricher,
        listing_filter: ListingFilter,
        scorer: DealScorer,
        store: ResultStore | None = None,
    ) -> None:
        self.config = config
        self.providers = providers
        self.enricher = enricher
        self.listing_filter = listing_filter
        self.scorer = scorer
        self.store = store

    @classmethod
    def from_config(
        cls,
        config: SearchConfig,
        providers: list[HardwareProvider],
        *,
        store: ResultStore | None = None,
    ) -> SearchService:
        return cls(
            config,
            providers,
            enricher=KnowledgeEnricher(),
            listing_filter=ListingFilter(config.search),
            scorer=DealScorer(config.search, config.scoring, config.upgrade_costs),
            store=store,
        )

    async def search(self) -> SearchRun:
        provider_outputs = await asyncio.gather(
            *(self._safe_search(provider) for provider in self.providers)
        )
        statuses = {provider.name: result for provider, result, _ in provider_outputs}
        listings = [listing for _, _, found in provider_outputs for listing in found]
        enriched = [self.enricher.enrich(listing) for listing in deduplicate(listings)]
        accepted: list[HardwareListing] = []
        cluster_candidates: list[RankedListing] = []
        rejected_count = 0
        for listing in enriched:
            specification_decision = self.listing_filter.evaluate(listing, enforce_quantity=False)
            if not specification_decision.accepted:
                rejected_count += 1
                continue
            listing.raw_attributes["warnings"] = specification_decision.warnings
            cluster_candidates.append(self._apply_trust(self.scorer.score(listing)))
            quantity_decision = self.listing_filter.evaluate(listing)
            if quantity_decision.accepted:
                listing.raw_attributes["warnings"] = quantity_decision.warnings
                accepted.append(listing)
            else:
                rejected_count += 1
        ranked = [self._apply_trust(self.scorer.score(listing)) for listing in accepted]
        ranked.sort(key=lambda item: item.score.total, reverse=True)
        cluster_deals = build_cluster_deals(
            cluster_candidates, self.config.search.quantity_required
        )
        run_id = await asyncio.to_thread(self.store.save, ranked) if self.store else None
        return SearchRun(
            ranked=ranked,
            cluster_deals=cluster_deals,
            provider_results=statuses,
            rejected_count=rejected_count,
            run_id=run_id,
        )

    async def _safe_search(
        self, provider: HardwareProvider
    ) -> tuple[HardwareProvider, ProviderResult, list[HardwareListing]]:
        try:
            listings = await provider.search(self.config.search)
        except ProviderUnsupported as error:
            return (
                provider,
                ProviderResult(status=ProviderStatus.UNSUPPORTED, message=str(error)),
                [],
            )
        except ProviderRateLimited as error:
            return (
                provider,
                ProviderResult(status=ProviderStatus.RATE_LIMITED, message=str(error)),
                [],
            )
        except ProviderUnavailable as error:
            return (
                provider,
                ProviderResult(status=ProviderStatus.UNAVAILABLE, message=str(error)),
                [],
            )
        except Exception as error:  # provider plugins are an isolation boundary
            logger.exception("unexpected provider failure: %s", provider.name)
            return provider, ProviderResult(status=ProviderStatus.ERROR, message=str(error)), []
        return (
            provider,
            ProviderResult(status=ProviderStatus.AVAILABLE, listing_count=len(listings)),
            listings,
        )

    def _apply_trust(self, ranked: RankedListing) -> RankedListing:
        provider = next(item for item in self.providers if item.name == ranked.listing.provider)
        if provider.trust_weight == 1:
            return ranked
        score = ranked.score.model_copy(
            update={
                "total": round(ranked.score.total * provider.trust_weight, 2),
                "explanation": [
                    *ranked.score.explanation,
                    f"- Provider trust multiplier: {provider.trust_weight:.2f}",
                ],
            }
        )
        return ranked.model_copy(update={"score": score})
