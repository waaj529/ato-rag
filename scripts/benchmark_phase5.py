#!/usr/bin/env python3
"""Run the Phase 5 grounded generation, citation verification and Jev judge benchmark."""

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import statistics
import sys
import time

import psycopg

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from services.generation import GenerationSettings
from packages.telemetry import LangfuseExporter
from packages.telemetry import (
    ModelObservation,
    get_current_trace_id,
    get_global_collector,
    record_model_observation,
    span,
    trace_context,
)
from scripts.probe_embedding_profile import dotenv_value
from services.context_builder import ContextBuilder, ContextSettings, Phase4Store
from services.embedding import IsaacusEmbeddingClient
from services.evaluation.generation import summarize_generation_benchmark
from services.evaluation.gold import gold_sha256, load_cases
from services.reranking import (
    ChildReranker,
    IsaacusRerankingClient,
    KanonRerankerAdapter,
    RerankingSettings,
)
from services.retrieval import HybridRetriever, SearchStore
from services.verification import GroundedAnswerPipeline

DEFAULT_DSN = "postgresql://fintaxgpt:fintaxgpt-local-only@127.0.0.1:5433/fintaxgpt"
DEFAULT_GOLD = ROOT / "evals/australia_tax_legal_gold.jsonl"
DEFAULT_Q_CACHE = ROOT / "data/embeddings/kanon2-768-v1/benchmark_query_vectors.json"
DEFAULT_K_CACHE = ROOT / "data/evaluations/cache/kanon_rerank_cache.json"
DEFAULT_OUTPUT = ROOT / f"data/evaluations/phase5_generation_{time.time_ns()}.json"

def _cache_key(query: str, texts: tuple[str, ...]) -> str:
    return hashlib.sha256((query + "||" + "|".join(texts)).encode()).hexdigest()

def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dsn", default=os.environ.get("FINTAX_DATABASE_URL", DEFAULT_DSN))
    parser.add_argument("--env", type=Path, default=ROOT / ".env")
    parser.add_argument("--gold", type=Path, default=DEFAULT_GOLD)
    parser.add_argument("--limit", type=int, default=300)
    args = parser.parse_args()

    GenerationSettings.from_env()
    exporter = LangfuseExporter.from_env()
    cases = load_cases(args.gold)[:args.limit]
    q_cache = json.loads(DEFAULT_Q_CACHE.read_text()) if DEFAULT_Q_CACHE.exists() else {}
    k_cache = json.loads(DEFAULT_K_CACHE.read_text()) if DEFAULT_K_CACHE.exists() else {}

    api_key = dotenv_value(args.env, "ISAACUS_API_KEY")
    raw_rerank, raw_embed = IsaacusRerankingClient(api_key), IsaacusEmbeddingClient(api_key)

    def cached_transport(request, timeout):
        payload = json.loads(request.data)
        key = _cache_key(payload["query"], tuple(payload["texts"]))
        if key not in k_cache:
            k_cache[key] = json.loads(raw_rerank._transport(request, timeout))
            DEFAULT_K_CACHE.write_text(json.dumps(k_cache))
        return json.dumps(k_cache[key]).encode()

    def get_query_vector(query: str) -> tuple[float, ...]:
        q_key = hashlib.sha256(query.encode()).hexdigest()
        if q_key not in q_cache:
            q_cache[q_key] = list(raw_embed.embed_query(query))
            DEFAULT_Q_CACHE.write_text(json.dumps(q_cache))
        else:
            record_model_observation(ModelObservation(
                provider="isaacus", model="kanon-2-embedder", model_revision="kanon-2-768-v1",
                task="query_embedding", trace_id=get_current_trace_id() or "",
                input_tokens=len(query.split()), latency_ms=0.5, cost=0.0, cache_hit=True, status="ok",
            ))
        return tuple(q_cache[q_key])

    kanon_adapter = KanonRerankerAdapter(IsaacusRerankingClient(api_key, transport=cached_transport))
    pipeline = GroundedAnswerPipeline()
    responses, latencies = [], []
    collector = get_global_collector()
    collector.clear()

    with psycopg.connect(args.dsn) as conn:
        retriever, store = HybridRetriever(SearchStore(conn)), Phase4Store(conn)
        reranker = ChildReranker(store, kanon_adapter, RerankingSettings(model="kanon-2-reranker"))
        builder = ContextBuilder(store, ContextSettings())

        for idx, case in enumerate(cases, 1):
            t0 = time.perf_counter()
            with trace_context(benchmark_case_id=case["id"], exporter=exporter):
                with span("answer_request"):
                    search_res = retriever.search(case["question"], get_query_vector, limit=80)
                    pkg = builder.build(reranker.rerank(search_res))
                    resp = pipeline.run(case["question"], pkg)
            latencies.append((time.perf_counter() - t0) * 1000)
            responses.append(resp)
            if idx % 50 == 0 or idx == len(cases):
                print(f"[{idx}/{len(cases)}] Processed Phase 5 cases...", flush=True)

    metrics = summarize_generation_benchmark(cases, responses)
    all_obs = collector.get_observations()
    gen_obs = [o for o in all_obs if o.task in {"generate", "repair"}]
    judge_obs = [o for o in all_obs if o.task == "judge"]
    total_cost = sum(o.cost or 0 for o in gen_obs + judge_obs)
    cost_known = all(o.cost is not None for o in gen_obs + judge_obs)

    report = {
        "schema_version": "fintax-phase5-eval-1.0",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "gold_sha256": gold_sha256(args.gold),
        "cases_evaluated": len(cases),
        "metrics": metrics,
        "timing_and_cost": {
            "p50_latency_ms": round(sorted(latencies)[len(latencies) // 2], 2),
            "p95_latency_ms": round(sorted(latencies)[int(len(latencies) * 0.95)], 2),
            "mean_latency_ms": round(statistics.fmean(latencies), 2),
            "total_generation_calls": len(gen_obs),
            "total_judge_calls": len(judge_obs),
            "total_cost_usd": round(total_cost, 4) if cost_known else None,
            "avg_cost_per_query_usd": round(total_cost / max(1, len(cases)), 6) if cost_known else None,
        },
    }
    with DEFAULT_OUTPUT.open("x") as handle:
        json.dump(report, handle, indent=2)
    print(f"\nSaved Phase 5 evaluation report to {DEFAULT_OUTPUT}")
    print(json.dumps(report["metrics"], indent=2))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
