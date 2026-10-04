"""Reciprocal-rank fusion for incompatible first-stage scores."""

from .models import Candidate, RetrievedChunk, RetrievalSettings


def reciprocal_rank_fusion(
    rankings: dict[str, tuple[Candidate, ...]], settings: RetrievalSettings,
    limit: int,
) -> tuple[RetrievedChunk, ...]:
    weights = {
        "exact": settings.exact_weight,
        "lexical": settings.lexical_weight,
        "dense": settings.dense_weight,
    }
    candidates: dict[str, Candidate] = {}
    scores: dict[str, float] = {}
    ranks: dict[str, dict[str, int]] = {}
    for retriever, values in rankings.items():
        for rank, candidate in enumerate(values, start=1):
            candidates[candidate.chunk_id] = candidate
            scores[candidate.chunk_id] = scores.get(candidate.chunk_id, 0.0) + (
                weights[retriever] / (settings.rrf_k + rank)
            )
            ranks.setdefault(candidate.chunk_id, {})[retriever] = rank
    ordered = sorted(scores, key=lambda chunk_id: (-scores[chunk_id], chunk_id))
    return tuple(
        RetrievedChunk(candidates[chunk_id], scores[chunk_id], ranks[chunk_id])
        for chunk_id in ordered[:limit]
    )
