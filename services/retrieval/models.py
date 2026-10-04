"""Typed records and versioned settings for Phase 3 retrieval."""

from dataclasses import dataclass, field


@dataclass(frozen=True)
class RetrievalSettings:
    profile_id: str = "kanon2-768-v1"
    exact_limit: int = 120
    lexical_limit: int = 200
    dense_limit: int = 100
    hnsw_ef_search: int = 1000
    rrf_k: int = 60
    exact_weight: float = 2.0
    lexical_weight: float = 1.0
    dense_weight: float = 1.0
    version: str = "phase3-rrf-v4"


@dataclass(frozen=True)
class Candidate:
    chunk_id: str
    document_id: str
    version_id: str
    source_locator: dict
    authority_rank: int | None
    retrieval_score: float


@dataclass(frozen=True)
class RetrievedChunk:
    candidate: Candidate
    rrf_score: float
    ranks: dict[str, int] = field(default_factory=dict)


@dataclass(frozen=True)
class SearchResult:
    query: str
    route: str
    identifiers: tuple[str, ...]
    chunks: tuple[RetrievedChunk, ...]
    settings_version: str
