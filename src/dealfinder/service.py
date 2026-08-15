"""Failure-isolated orchestration of independent providers and deal processing."""

from __future__ import annotations

import asyncio
import logging
from enum import StrEnum

from pydantic import BaseModel

from dealfinder.config import SearchConfig
from dealfinder.deduplication import deduplicate
from dealfinder.enrichment import KnowledgeEnricher
from dealfinder.filtering import ListingFilter
from dealfinder.models import HardwareListing, RankedListing
from dealfinder.providers.base import (
    HardwareProvider,
    ProviderRateLimited,
    ProviderUnavailable,
)
from dealfinder.scoring import DealScorer

logger = logging.getLogger(__name__)


class ProviderStatus(StrEnum):
    AVAILABLE = "available"
    UNAVAILABLE = "unavailable"
    RATE_LIMITED = "rate_limited"
    ERROR = "error"


class ProviderResult(BaseModel):
    status: ProviderStatus
    listing_count: int = 0
    message: str | None = None


class SearchRun(BaseModel):
    ranked: list[RankedListing]
    provider_results: dict[str, ProviderResult]
    rejected_count: int = 0


class SearchService:
    def __init__(
        self,
        config: SearchConfig,
        providers: list[HardwareProvider],
        *,
        enricher: KnowledgeEnricher,
        listing_filter: ListingFilter,
        scorer: DealScorer,
    ) -> None:
        self.config = config
        self.providers = providers
        self.enricher = enricher
        self.listing_filter = listing_filter
        self.scorer = scorer

    @classmethod
    def from_config(cls, config: SearchConfig, providers: list[HardwareProvider]) -> SearchService:
        return cls(
            config,
            providers,
            enricher=KnowledgeEnricher(),
            listing_filter=ListingFilter(config.search),
            scorer=DealScorer(config.search, config.scoring, config.upgrade_costs),
        )

    async def search(self) -> SearchRun:
        provider_outputs = await asyncio.gather(
            *(self._safe_search(provider) for provider in self.providers)
        )
        statuses = {provider.name: result for provider, result, _ in provider_outputs}
        listings = [listing for _, _, found in provider_outputs for listing in found]
        enriched = [self.enricher.enrich(listing) for listing in deduplicate(listings)]
        accepted: list[HardwareListing] = []
        rejected_count = 0
        for listing in enriched:
            decision = self.listing_filter.evaluate(listing)
            if decision.accepted:
                listing.raw_attributes["warnings"] = decision.warnings
                accepted.append(listing)
            else:
                rejected_count += 1
        ranked = [self._apply_trust(self.scorer.score(listing)) for listing in accepted]
        ranked.sort(key=lambda item: item.score.total, reverse=True)
        return SearchRun(
            ranked=ranked,
            provider_results=statuses,
            rejected_count=rejected_count,
        )

    async def _safe_search(
        self, provider: HardwareProvider
    ) -> tuple[HardwareProvider, ProviderResult, list[HardwareListing]]:
        try:
            listings = await provider.search(self.config.search)
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
