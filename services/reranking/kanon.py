"""Isaacus Kanon 2 reranker adapter with Langfuse/OTel tracing."""

import time
from typing import Sequence

from packages.telemetry import (
    ModelObservation,
    calculate_model_cost,
    get_current_trace_id,
    record_model_observation,
)
from .client import IsaacusRerankingClient
from .models import HydratedCandidate, RerankedChild


class KanonRerankerAdapter:
    def __init__(self, client: IsaacusRerankingClient,
                 revision: str = "2026-kanon-2") -> None:
        self.client = client
        self._revision = revision

    @property
    def provider_name(self) -> str:
        return "isaacus"

    @property
    def model_name(self) -> str:
        return self.client.model

    @property
    def revision(self) -> str:
        return self._revision

    def rerank_candidates(
        self, query: str, candidates: Sequence[HydratedCandidate], top_n: int
    ) -> tuple[tuple[RerankedChild, ...], int]:
        if not candidates:
            return (), 0
        texts = [c.content_for_reranking for c in candidates]
        pre_ranks = {
            c.retrieved.candidate.chunk_id: idx for idx, c in enumerate(candidates, 1)
        }
        started = time.perf_counter()
        try:
            batch = self.client.rerank(query, texts, min(top_n, len(candidates)))
            children = tuple(
                RerankedChild(candidates[idx], score, rank)
                for rank, (idx, score) in enumerate(batch.results, 1)
            )
            latency_ms = round((time.perf_counter() - started) * 1000, 2)
            self._log_observation(
                candidates, children, pre_ranks, batch.input_tokens, latency_ms, "ok"
            )
            return children, batch.input_tokens
        except Exception as exc:
            latency_ms = round((time.perf_counter() - started) * 1000, 2)
            self._log_observation(
                candidates, (), pre_ranks, 0, latency_ms, "error", str(exc)
            )
            raise

    def _log_observation(
        self,
        candidates: Sequence[HydratedCandidate],
        children: tuple[RerankedChild, ...],
        pre_ranks: dict[str, int],
        input_tokens: int,
        latency_ms: float,
        status: str,
        error_msg: str | None = None,
    ) -> None:
        cost = calculate_model_cost(self.model_name, input_tokens)
        post_ranks = {
            c.candidate.retrieved.candidate.chunk_id: c.reranker_rank for c in children
        }
        scores = {
            c.candidate.retrieved.candidate.chunk_id: c.reranker_score for c in children
        }
        record_model_observation(ModelObservation(
            provider=self.provider_name,
            model=self.model_name,
            model_revision=self.revision,
            task="rerank",
            trace_id=get_current_trace_id() or "",
            input_tokens=input_tokens,
            latency_ms=latency_ms,
            cost=cost,
            status=status,
            metadata={
                "candidate_count_in": len(candidates),
                "candidate_count_out": len(children),
                "candidate_chunk_ids": [c.retrieved.candidate.chunk_id for c in candidates],
                "pre_rerank_ranks": pre_ranks,
                "post_rerank_ranks": post_ranks,
                "scores": scores,
                "error": error_msg,
            },
        ))
