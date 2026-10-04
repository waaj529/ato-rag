#!/usr/bin/env python3
"""Execute and trace organic queries during the staging / real-user trial."""

import argparse
from dataclasses import asdict
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

from packages.security import DEFAULT_PUBLIC_SCOPE, ScopeSafetyPolicyGate
from services.generation import GenerationSettings
from packages.telemetry import LangfuseExporter
from packages.telemetry import (
    get_current_trace_id,
    get_global_collector,
    span,
    trace_context,
)
from scripts.probe_embedding_profile import dotenv_value
from services.context_builder import ContextBuilder, ContextSettings, Phase4Store
from services.embedding import IsaacusEmbeddingClient
from services.evaluation import (
    StagingQueryRecord,
    StagingUserFeedback,
    log_staging_record,
)
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
Q_CACHE = ROOT / "data/embeddings/kanon2-768-v1/benchmark_query_vectors.json"
K_CACHE = ROOT / "data/evaluations/cache/kanon_rerank_cache.json"

def execute_staging_query(
    query: str,
    conn: psycopg.Connection,
    api_key: str,
    feedback: StagingUserFeedback | None = None,
) -> StagingQueryRecord:
    GenerationSettings.from_env()
    exporter = LangfuseExporter.from_env()
    q_cache = json.loads(Q_CACHE.read_text()) if Q_CACHE.exists() else {}
    k_cache = json.loads(K_CACHE.read_text()) if K_CACHE.exists() else {}
    raw_rerank, raw_embed = IsaacusRerankingClient(api_key), IsaacusEmbeddingClient(api_key)

    def cached_transport(req, timeout):
        payload = json.loads(req.data)
        key = hashlib.sha256((payload["query"] + "||" + "|".join(payload["texts"])).encode()).hexdigest()
        if key not in k_cache:
            k_cache[key] = json.loads(raw_rerank._transport(req, timeout))
            K_CACHE.write_text(json.dumps(k_cache))
        return json.dumps(k_cache[key]).encode()

    def embed_vector(q: str):
        q_key = hashlib.sha256(q.encode()).hexdigest()
        if q_key not in q_cache:
            q_cache[q_key] = list(raw_embed.embed_query(q))
            Q_CACHE.write_text(json.dumps(q_cache))
        return tuple(q_cache[q_key])

    kanon_adapter = KanonRerankerAdapter(IsaacusRerankingClient(api_key, transport=cached_transport))
    retriever, store = HybridRetriever(SearchStore(conn)), Phase4Store(conn)
    reranker = ChildReranker(store, kanon_adapter, RerankingSettings(model="kanon-2-reranker"))
    builder = ContextBuilder(store, ContextSettings())
    pipeline = GroundedAnswerPipeline()
    policy_gate, scope_gate = ScopeSafetyPolicyGate(), CorpusScopeGate()

    qid = f"staging-{int(time.time() * 1000)}"
    t0 = time.perf_counter()
    collector = get_global_collector()
    collector.clear()

    with trace_context(exporter=exporter):
        with span("staging_query_session"):
            trace_id = get_current_trace_id() or ""
            policy_dec = policy_gate.evaluate(query)
            if not policy_dec.passed:
                resp = GroundedAnswerPipeline.policy_refusal(query, policy_dec.code, policy_dec.reason)
                final_dec, scope_reason, adequacy_reason = "safety-refused", None, None
                authorities, scores = (), ()
            else:
                scope_dec = scope_gate.evaluate(query)
                if scope_dec.status == ScopeStatus.OUT_OF_CORPUS:
                    resp = GroundedAnswerPipeline.scope_refusal(query, scope_dec.code, scope_dec.reason)
                    final_dec, scope_reason, adequacy_reason = "out-of-corpus", scope_dec.reason, None
                    authorities, scores = (), ()
                else:
                    scope_reason = scope_dec.reason
                    search_res = retriever.search(query, embed_vector, limit=80, permission_scope=DEFAULT_PUBLIC_SCOPE)
                    reranked = reranker.rerank(search_res)
                    context = builder.build(reranked)
                    resp = pipeline.run(query, context, permission_scope=DEFAULT_PUBLIC_SCOPE)
                    authorities = tuple(u.citation_label for u in context.evidence if u.citation_label)
                    scores = tuple(round(u.reranker_score or 0.0, 4) for u in context.evidence)
                    adequacy_reason = resp.decision_reason
                    final_dec = "answered" if not resp.abstained else "inadequate-evidence"

            lat = (time.perf_counter() - t0) * 1000
            observations = collector.get_observations()
            cost = sum(o.cost or 0 for o in observations)
            generation_model = next(
                (o.model for o in observations if o.task in {"generate", "repair"}),
                "not-called",
            )
            record = StagingQueryRecord(
                query_id=qid, query=query, timestamp=datetime.now(timezone.utc).isoformat(),
                final_decision=final_dec, corpus_scope_reason=scope_reason,
                evidence_adequacy_reason=adequacy_reason, retrieved_authorities=authorities,
                reranker_scores=scores,
                generation_model=generation_model,
                judge_decision=asdict(resp.judge),
                latency_ms=round(lat, 2), cost_usd=round(cost, 6) if all(o.cost is not None for o in observations) else None, trace_id=trace_id, user_feedback=feedback,
            )
            log_staging_record(record)
    return record

def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--query", type=str, help="Single query to test in staging")
    parser.add_argument("--dsn", default=os.environ.get("FINTAX_DATABASE_URL", DEFAULT_DSN))
    parser.add_argument("--env", type=Path, default=ROOT / ".env")
    args = parser.parse_args()
    api_key = dotenv_value(args.env, "ISAACUS_API_KEY")
    if not args.query:
        print("Please provide a --query string to execute in staging.")
        return 1
    with psycopg.connect(args.dsn) as conn:
        rec = execute_staging_query(args.query, conn, api_key)
    print(json.dumps(rec.to_dict(), indent=2))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
