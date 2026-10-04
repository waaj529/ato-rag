"""Evaluation harness and summary aggregation for reranker benchmarking."""

from dataclasses import dataclass, field
import statistics
from typing import Sequence

from .metrics import evidence_retention_rate, ndcg_at_k, recall_at_k, reciprocal_rank


@dataclass
class CaseEvaluation:
    case_id: str
    is_abstention: bool
    phase3_rank: int | None
    heuristic_rank: int | None
    kanon_rank: int | None
    phase3_rels: list[int] = field(default_factory=list)
    heuristic_rels: list[int] = field(default_factory=list)
    kanon_rels: list[int] = field(default_factory=list)
    heuristic_latency_ms: float = 0.0
    kanon_latency_ms: float = 0.0
    heuristic_tokens: int = 0
    kanon_tokens: int = 0
    heuristic_cost: float = 0.0
    kanon_cost: float = 0.0


def check_candidate_match(cand, passages: list[dict]) -> bool:
    for passage in passages:
        if cand.document_id != passage.get("document_id"):
            continue
        if cand.version_id != passage.get("version_id"):
            continue
        loc = cand.source_locator
        if loc.get("section_id") != passage.get("section_id"):
            continue
        s, e = loc.get("char_start"), loc.get("char_end")
        if isinstance(s, int) and isinstance(e, int):
            if s <= passage.get("char_start", -1) and e >= passage.get("char_end", -1):
                return True
        elif loc.get("table_id") == passage.get("table_id"):
            return True
    return False


def evaluate_candidates(case: dict, candidates: Sequence) -> tuple[int | None, list[int]]:
    if case.get("must_abstain"):
        return (1 if not candidates else None), ([1] if not candidates else [0] * len(candidates))
    passages = case.get("expected_passages") or []
    rels: list[int] = []
    first_rank: int | None = None
    for idx, item in enumerate(candidates, 1):
        cand = getattr(item, "candidate", item)
        cand = getattr(cand, "candidate", cand)
        cand = getattr(cand, "retrieved", cand)
        cand = getattr(cand, "candidate", cand)
        is_hit = 1 if check_candidate_match(cand, passages) else 0
        rels.append(is_hit)
        if is_hit and first_rank is None:
            first_rank = idx
    return first_rank, rels


def summarize_model(ranks: list[int | None], rels_list: list[list[int]],
                    latencies: list[float], tokens: list[int], costs: list[float],
                    phase3_ranks: list[int | None]) -> dict:
    pct = lambda vals, p: sorted(vals)[min(len(vals) - 1, round((len(vals) - 1) * p))] if vals else 0.0
    return {
        "mrr": round(reciprocal_rank(ranks), 4),
        "ndcg_at_5": round(ndcg_at_k(rels_list, 5), 4),
        "ndcg_at_10": round(ndcg_at_k(rels_list, 10), 4),
        "ndcg_at_20": round(ndcg_at_k(rels_list, 20), 4),
        "recall_at_5": round(recall_at_k(ranks, 5), 4),
        "recall_at_10": round(recall_at_k(ranks, 10), 4),
        "recall_at_20": round(recall_at_k(ranks, 20), 4),
        "recall_at_50": round(recall_at_k(ranks, 50), 4),
        "evidence_retention_rate": round(evidence_retention_rate(phase3_ranks, ranks), 4),
        "latency_ms": {"mean": round(statistics.fmean(latencies), 2), "p50": round(pct(latencies, 0.50), 2),
                       "p95": round(pct(latencies, 0.95), 2)},
        "avg_tokens_per_query": round(statistics.fmean(tokens), 1),
        "total_tokens": sum(tokens),
        "avg_cost_per_query": round(statistics.fmean(costs), 6),
        "total_cost": round(sum(costs), 4),
    }
