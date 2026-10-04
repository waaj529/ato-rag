"""Bounded Phase 4 child reranking over the frozen Phase 3 output."""

from typing import Any

from packages.telemetry import span
from .dedupe import dedupe_candidates
from .models import (
    HydratedCandidate,
    RerankedChild,
    RerankingResult,
    RerankingSettings,
)


class CandidateHydrator:
    def hydrate(self, chunks) -> tuple[HydratedCandidate, ...]:
        raise NotImplementedError


class ChildReranker:
    def __init__(
        self,
        hydrator: CandidateHydrator,
        adapter: Any,
        settings: RerankingSettings = RerankingSettings(),
    ) -> None:
        self.hydrator = hydrator
        self.adapter = adapter
        self.settings = settings

    def rerank(self, search_result) -> RerankingResult:
        with span("reranking", {"model": self.settings.model, "version": self.settings.version}):
            selected = search_result.chunks[: self.settings.candidate_limit]
            hydrated = self.hydrator.hydrate(selected)
            deduped = dedupe_candidates(hydrated, self.settings.near_duplicate_threshold)
            if not deduped:
                return RerankingResult(search_result.query, (), 0, self.settings.version)
            top_n = min(self.settings.child_limit, len(deduped))
            if hasattr(self.adapter, "rerank_candidates"):
                children, tokens = self.adapter.rerank_candidates(
                    search_result.query, deduped, top_n
                )
            else:
                batch = self.adapter.rerank(
                    search_result.query,
                    [cand.content_for_reranking for cand in deduped],
                    top_n,
                )
                children = tuple(
                    RerankedChild(deduped[index], score, rank)
                    for rank, (index, score) in enumerate(batch.results, 1)
                )
                tokens = batch.input_tokens
            model_name = getattr(self.adapter, "model_name", self.settings.model)
            return RerankingResult(
                search_result.query, children, tokens, self.settings.version, model=model_name
            )
