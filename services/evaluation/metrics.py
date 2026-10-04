"""Information retrieval evaluation metrics: NDCG, MRR, Recall and Retention."""

import math
from typing import Sequence


def reciprocal_rank(ranks: Sequence[int | None]) -> float:
    scores = [1.0 / r for r in ranks if r is not None and r > 0]
    return sum(scores) / max(1, len(ranks))


def recall_at_k(ranks: Sequence[int | None], k: int) -> float:
    hits = sum(1 for r in ranks if r is not None and 1 <= r <= k)
    return hits / max(1, len(ranks))


def ndcg_at_k(binary_relevances: Sequence[Sequence[int]], k: int) -> float:
    """Calculate mean NDCG@k across queries given binary relevance list per query."""
    if not binary_relevances:
        return 0.0
    scores: list[float] = []
    idcg_table = [1.0 / math.log2(i + 2) for i in range(k)]

    for rel_list in binary_relevances:
        trimmed = list(rel_list[:k])
        dcg = sum(
            rel / math.log2(idx + 2) for idx, rel in enumerate(trimmed) if rel > 0
        )
        total_relevant = sum(rel_list)
        ideal_count = min(k, total_relevant)
        idcg = sum(idcg_table[:ideal_count])
        if idcg <= 0.0:
            scores.append(1.0 if dcg == 0.0 else 0.0)
        else:
            scores.append(dcg / idcg)
    return sum(scores) / len(scores)


def evidence_retention_rate(
    phase3_ranks: Sequence[int | None],
    rerank_ranks: Sequence[int | None],
    phase3_cutoff: int = 80,
    rerank_cutoff: int = 20,
) -> float:
    """Retention: fraction of cases with evidence in phase3 that retain it in top rerank cutoff."""
    present_in_input = 0
    retained_in_output = 0
    for p_rank, r_rank in zip(phase3_ranks, rerank_ranks):
        if p_rank is not None and 1 <= p_rank <= phase3_cutoff:
            present_in_input += 1
            if r_rank is not None and 1 <= r_rank <= rerank_cutoff:
                retained_in_output += 1
    return retained_in_output / max(1, present_in_input)
