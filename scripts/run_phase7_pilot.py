"""Run Phase 7 controlled pilot across public Australian tax/legal workflows."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import psycopg
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from packages.security import DEFAULT_PUBLIC_SCOPE, ScopeSafetyPolicyGate
from services.generation import GenerationSettings
from packages.telemetry import LangfuseExporter
from packages.telemetry import (
    ModelObservation,
    get_current_trace_id,
    get_global_collector,
    record_model_observation,
    trace_context,
)
from scripts.probe_embedding_profile import dotenv_value
from services.context_builder import ContextBuilder, ContextSettings, Phase4Store
from services.embedding import IsaacusEmbeddingClient
from services.evaluation import classify_acceptance, compute_pilot_metrics, simulate_pilot_feedback
from services.reranking import (
    ChildReranker,
    IsaacusRerankingClient,
    KanonRerankerAdapter,
    RerankingSettings,
)
from services.retrieval import HybridRetriever, SearchStore
from services.source_registry import CorpusScopeGate, ScopeStatus
from services.verification import GroundedAnswerPipeline
DEFAULT_DSN = "postgresql://fintaxgpt:fintaxgpt-local-only@127.0.0.1:5433/fintaxgpt"
PILOT_CASES = ROOT / "evals/phase7/pilot_cases.jsonl"
DEFAULT_OUTPUT = ROOT / f"data/evaluations/phase7_pilot_{time.time_ns()}.json"
Q_CACHE = ROOT / "data/embeddings/kanon2-768-v1/benchmark_query_vectors.json"
K_CACHE = ROOT / "data/evaluations/cache/kanon_rerank_cache.json"
def run_pilot(dsn: str, cases_path: Path, env_path: Path, output_path: Path) -> dict:
    settings = GenerationSettings.from_env()
    exporter = LangfuseExporter.from_env()
    if output_path.exists():
        raise FileExistsError("Historical reports must not be overwritten")
    cases = [json.loads(line) for line in cases_path.read_text().splitlines() if line.strip()]
    q_cache = json.loads(Q_CACHE.read_text()) if Q_CACHE.exists() else {}
    k_cache = json.loads(K_CACHE.read_text()) if K_CACHE.exists() else {}
    api_key = dotenv_value(env_path, "ISAACUS_API_KEY")
    raw_rerank, raw_embed = IsaacusRerankingClient(api_key), IsaacusEmbeddingClient(api_key)
    def cached_transport(req, timeout):
        payload = json.loads(req.data)
        key = hashlib.sha256((payload["query"] + "||" + "|".join(payload["texts"])).encode()).hexdigest()
        if key not in k_cache:
            k_cache[key] = json.loads(raw_rerank._transport(req, timeout))
            K_CACHE.write_text(json.dumps(k_cache))
        return json.dumps(k_cache[key]).encode()
    def embed_vector(query: str):
        q_key = hashlib.sha256(query.encode()).hexdigest()
        if q_key not in q_cache:
            q_cache[q_key] = list(raw_embed.embed_query(query))
            Q_CACHE.write_text(json.dumps(q_cache))
        else:
            record_model_observation(ModelObservation(
                provider="isaacus", model="kanon-2-embedder", model_revision="kanon-2-768-v1",
                task="query_embedding", trace_id=get_current_trace_id() or "",
                input_tokens=len(query.split()), latency_ms=0.5, cost=0.0, cache_hit=True, status="ok",
            ))
        return tuple(q_cache[q_key])
    kanon_adapter = KanonRerankerAdapter(IsaacusRerankingClient(api_key, transport=cached_transport))
    pipeline, policy_gate, scope_gate = GroundedAnswerPipeline(), ScopeSafetyPolicyGate(), CorpusScopeGate()
    responses, feedbacks, latencies = [], [], []
    collector = get_global_collector()
    collector.clear()
    with psycopg.connect(dsn) as conn:
        retriever, store = HybridRetriever(SearchStore(conn)), Phase4Store(conn)
        reranker = ChildReranker(store, kanon_adapter, RerankingSettings(model="kanon-2-reranker"))
        builder = ContextBuilder(store, ContextSettings())
        for idx, case in enumerate(cases, 1):
            t0 = time.perf_counter()
            with trace_context(benchmark_case_id=case["id"], exporter=exporter):
                query = case["question"]
                policy_dec = policy_gate.evaluate(query)
                if not policy_dec.passed:
                    resp = GroundedAnswerPipeline.policy_refusal(query, policy_dec.code, policy_dec.reason)
                else:
                    scope_dec = scope_gate.evaluate(query)
                    if scope_dec.status == ScopeStatus.OUT_OF_CORPUS:
                        resp = GroundedAnswerPipeline.scope_refusal(query, scope_dec.code, scope_dec.reason)
                    else:
                        search_res = retriever.search(query, embed_vector, limit=80, permission_scope=DEFAULT_PUBLIC_SCOPE)
                        reranked = reranker.rerank(search_res)
                        context = builder.build(reranked)
                        resp = pipeline.run(query, context, permission_scope=DEFAULT_PUBLIC_SCOPE)
            latencies.append((time.perf_counter() - t0) * 1000)
            responses.append(resp)
            feedbacks.append(simulate_pilot_feedback(case, resp))
    metrics = compute_pilot_metrics(cases, responses, feedbacks, latencies, collector)
    status, gate_evaluations = classify_acceptance(metrics)
    benchmark_sha = hashlib.sha256(cases_path.read_bytes()).hexdigest()
    try:
        git_commit = subprocess.check_output(["git", "rev-parse", "HEAD"], stderr=subprocess.DEVNULL).decode().strip()
    except Exception:
        git_commit = "unknown"
    report = {
        "schema_version": "fintax-phase7-pilot-report-1.0",
        "run_id": f"phase7-pilot-{benchmark_sha[:10]}-{int(time.time())}",
        "git_commit": git_commit,
        "benchmark_sha256": benchmark_sha,
        "cache_mode": "hybrid_warm_cache",
        "model_versions": {
            "embeddings": "kanon-2-768-v1",
            "reranker": "kanon-2-reranker",
            "generation": settings.model,
            "judge": "heuristic-evidence-judge",
        },
        "created_at": datetime.now(timezone.utc).isoformat(),
        "status": status,
        "gate_evaluations": gate_evaluations,
        "cases_evaluated": len(cases),
        "metrics": metrics,
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("x") as handle:
        json.dump(report, handle, indent=2, sort_keys=True)
    return report
def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dsn", default=os.environ.get("FINTAX_DATABASE_URL", DEFAULT_DSN))
    parser.add_argument("--cases", type=Path, default=PILOT_CASES)
    parser.add_argument("--env", type=Path, default=ROOT / ".env")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    report = run_pilot(args.dsn, args.cases, args.env, args.output)
    print(json.dumps(report, indent=2))
    return 0
if __name__ == "__main__":
    raise SystemExit(main())
