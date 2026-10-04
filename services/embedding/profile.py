"""Versioned Kanon 2 embedding profile contract."""

from dataclasses import dataclass


@dataclass(frozen=True)
class EmbeddingProfile:
    profile_id: str
    provider: str
    model: str
    dimensions: int
    document_task: str
    query_task: str
    overflow_strategy: None
    normalization: str
    status: str

    def validate(self) -> None:
        if self.dimensions != 768:
            raise ValueError("Phase 3 baseline requires 768 dimensions")
        if self.document_task != "retrieval/document":
            raise ValueError("invalid document embedding task")
        if self.query_task != "retrieval/query":
            raise ValueError("invalid query embedding task")
        if self.overflow_strategy is not None:
            raise ValueError("overflow must fail rather than truncate legal evidence")


KANON2_768_V1 = EmbeddingProfile(
    profile_id="kanon2-768-v1",
    provider="isaacus",
    model="kanon-2-embedder",
    dimensions=768,
    document_task="retrieval/document",
    query_task="retrieval/query",
    overflow_strategy=None,
    normalization="l2_normalized_verified_2026-09-24",
    status="provisional",
)
