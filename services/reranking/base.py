"""Provider-neutral reranker adapter protocol."""

from typing import Protocol, Sequence

from .models import HydratedCandidate, RerankedChild


class RerankerAdapter(Protocol):
    @property
    def provider_name(self) -> str:
        ...

    @property
    def model_name(self) -> str:
        ...

    @property
    def revision(self) -> str:
        ...

    def rerank_candidates(
        self,
        query: str,
        candidates: Sequence[HydratedCandidate],
        top_n: int,
    ) -> tuple[tuple[RerankedChild, ...], int]:
        """Rerank candidates and return (ranked_children, input_tokens)."""
        ...
