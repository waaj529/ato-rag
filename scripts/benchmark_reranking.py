#!/usr/bin/env python3
"""Run the head-to-head Jev vs Kanon 2 reranker benchmark on frozen Phase 3 candidates."""

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import sys
import time

import psycopg

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from packages.telemetry import trace_context
from scripts.probe_embedding_profile import dotenv_value
from services.context_builder import Phase4Store
from services.embedding import IsaacusEmbeddingClient
from services.evaluation.gold import gold_sha256, load_cases
from services.evaluation.metrics import ndcg_at_k, recall_at_k, reciprocal_rank
from services.evaluation.reranking import CaseEvaluation, evaluate_candidates, summarize_model
from services.reranking import (
    IsaacusRerankingClient,
    HeuristicReranker,
    KanonRerankerAdapter,
    RerankingSettings,
)
from services.reranking.dedupe import dedupe_candidates
from services.retrieval import HybridRetriever, SearchStore

DEFAULT_DSN = "postgresql://fintaxgpt:fintaxgpt-local-only@127.0.0.1:5433/fintaxgpt"
DEFAULT_GOLD = ROOT / "evals/australia_tax_legal_gold.jsonl"
DEFAULT_Q_CACHE = ROOT / "data/embeddings/kanon2-768-v1/benchmark_query_vectors.json"
DEFAULT_K_CACHE = ROOT / "data/evaluations/cache/kanon_rerank_cache.json"
DEFAULT_OUTPUT = ROOT / f"data/evaluations/heuristic_reranker_comparison_{time.time_ns()}.json"


def _cache_key(query: str, texts: tuple[str, ...]) -> str:
    return hashlib.sha256((query + "||" + "|".join(texts)).encode()).hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dsn", default=os.environ.get("FINTAX_DATABASE_URL", DEFAULT_DSN))
    parser.add_argument("--env", type=Path, default=ROOT / ".env")
    parser.add_argument("--gold", type=Path, default=DEFAULT_GOLD)
    parser.add_argument("--limit", type=int, default=300)
    args = parser.parse_args()

    cases = load_cases(args.gold)[:args.limit]
    q_cache = json.loads(DEFAULT_Q_CACHE.read_text()) if DEFAULT_Q_CACHE.exists() else {}
    DEFAULT_K_CACHE.parent.mkdir(parents=True, exist_ok=True)
    k_cache = json.loads(DEFAULT_K_CACHE.read_text()) if DEFAULT_K_CACHE.exists() else {}

    api_key = dotenv_value(args.env, "ISAACUS_API_KEY")
    raw_kanon, raw_embed = IsaacusRerankingClient(api_key), IsaacusEmbeddingClient(api_key)

    def cached_transport(request, timeout):
        payload = json.loads(request.data)
        key = _cache_key(payload["query"], tuple(payload["texts"]))
        if key not in k_cache:
            k_cache[key] = json.loads(raw_kanon._transport(request, timeout))
            DEFAULT_K_CACHE.write_text(json.dumps(k_cache))
        return json.dumps(k_cache[key]).encode()

    def get_query_vector(query: str) -> tuple[float, ...]:
        q_key = hashlib.sha256(query.encode()).hexdigest()
        if q_key not in q_cache:
            q_cache[q_key] = list(raw_embed.embed_query(query))
            DEFAULT_Q_CACHE.write_text(json.dumps(q_cache))
        return tuple(q_cache[q_key])

    kanon_adapter = KanonRerankerAdapter(IsaacusRerankingClient(api_key, transport=cached_transport))
    heuristic_adapter, settings, evals = HeuristicReranker(), RerankingSettings(), []

    with psycopg.connect(args.dsn) as conn:
        retriever, store = HybridRetriever(SearchStore(conn)), Phase4Store(conn)
        for num, case in enumerate(cases, 1):
            with trace_context(benchmark_case_id=case["id"]):
                res = retriever.search(case["question"], get_query_vector, limit=settings.candidate_limit)
                p3_rank, p3_rels = evaluate_candidates(case, res.chunks)
                deduped = dedupe_candidates(store.hydrate(res.chunks[:settings.candidate_limit]), settings.near_duplicate_threshold)

                t0 = time.perf_counter()
                j_ch, j_tok = heuristic_adapter.rerank_candidates(case["question"], deduped, settings.child_limit)
                j_lat = (time.perf_counter() - t0) * 1000
                j_rank, j_rels = evaluate_candidates(case, j_ch)

                t1 = time.perf_counter()
                k_ch, k_tok = kanon_adapter.rerank_candidates(case["question"], deduped, settings.child_limit)
                k_lat = (time.perf_counter() - t1) * 1000
                k_rank, k_rels = evaluate_candidates(case, k_ch)

                evals.append(CaseEvaluation(
                    case_id=case["id"], is_abstention=bool(case.get("must_abstain")),
                    phase3_rank=p3_rank, heuristic_rank=j_rank, kanon_rank=k_rank,
                    phase3_rels=p3_rels, heuristic_rels=j_rels, kanon_rels=k_rels,
                    heuristic_latency_ms=j_lat, kanon_latency_ms=k_lat, heuristic_tokens=j_tok, kanon_tokens=k_tok,
                    heuristic_cost=0.0, kanon_cost=(k_tok / 1_000_000) * 0.35,
                ))
            if num % 50 == 0 or num == len(cases):
                print(f"[{num}/{len(cases)}] Processed cases...", flush=True)

    DEFAULT_K_CACHE.write_text(json.dumps(k_cache))
    p3_ranks = [e.phase3_rank for e in evals]
    j_sum = summarize_model([e.heuristic_rank for e in evals], [e.heuristic_rels for e in evals],
                            [e.heuristic_latency_ms for e in evals], [e.heuristic_tokens for e in evals], [e.heuristic_cost for e in evals], p3_ranks)
    k_sum = summarize_model([e.kanon_rank for e in evals], [e.kanon_rels for e in evals],
                            [e.kanon_latency_ms for e in evals], [e.kanon_tokens for e in evals], [e.kanon_cost for e in evals], p3_ranks)

    report = {
        "schema_version": "fintax-phase4-reranker-eval-1.0", "created_at": datetime.now(timezone.utc).isoformat(),
        "gold_sha256": gold_sha256(args.gold), "cases_evaluated": len(evals),
        "phase3_retrieval_baseline": {
            "mrr": round(reciprocal_rank(p3_ranks), 4), "ndcg_at_20": round(ndcg_at_k([e.phase3_rels for e in evals], 20), 4),
            "recall_at_20": round(recall_at_k(p3_ranks, 20), 4), "recall_at_80": round(recall_at_k(p3_ranks, 80), 4),
        },
        "heuristic_decision_reranker": j_sum, "kanon_2_reranker": k_sum,
        "comparison": {
            "heuristic_wins": len([e for e in evals if e.heuristic_rank and (not e.kanon_rank or e.kanon_rank > 20)]),
            "kanon_wins": len([e for e in evals if e.kanon_rank and (not e.heuristic_rank or e.heuristic_rank > 20)]),
        },
    }
    with DEFAULT_OUTPUT.open("x") as handle:
        json.dump(report, handle, indent=2)
    print(f"\nReport: {DEFAULT_OUTPUT}\nNDCG@20: Heuristic={j_sum['ndcg_at_20']} vs Kanon={k_sum['ndcg_at_20']}\nMRR: Heuristic={j_sum['mrr']} vs Kanon={k_sum['mrr']}\nRecall@20: Heuristic={j_sum['recall_at_20']} vs Kanon={k_sum['recall_at_20']}\nRetention: Heuristic={j_sum['evidence_retention_rate']} vs Kanon={k_sum['evidence_retention_rate']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
