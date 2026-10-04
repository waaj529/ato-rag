"""Typed Phase 4 reranking records, decision signals and settings."""

from dataclasses import dataclass
from typing import Optional

from services.retrieval import RetrievedChunk


@dataclass(frozen=True)
class RelevanceSignals:
    relevant: float
    answer_bearing: float
    authority_fit: float
    temporal_fit: float

    def composite_score(self) -> float:
        return round(
            0.45 * self.relevant
            + 0.30 * self.answer_bearing
            + 0.15 * self.authority_fit
            + 0.10 * self.temporal_fit,
            6,
        )


@dataclass(frozen=True)
class RerankingSettings:
    model: str = "kanon-2-reranker"
    candidate_limit: int = 80
    child_limit: int = 20
    near_duplicate_threshold: float = 0.95
    version: str = "phase4-kanon2-v1"


@dataclass(frozen=True)
class HydratedCandidate:
    retrieved: RetrievedChunk
    parent_chunk_id: str
    source_class: str
    canonical_reference_id: str | None
    contextual_header: str
    content: str
    content_for_reranking: str


@dataclass(frozen=True)
class RerankedChild:
    candidate: HydratedCandidate
    reranker_score: float
    reranker_rank: int
    signals: Optional[RelevanceSignals] = None


@dataclass(frozen=True)
class RerankingResult:
    query: str
    children: tuple[RerankedChild, ...]
    input_tokens: int
    settings_version: str
    model: str = ""
