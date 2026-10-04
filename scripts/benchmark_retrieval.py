#!/usr/bin/env python3
"""Run the provisional 300-case Phase 3 hybrid-retrieval benchmark."""

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import statistics
import sys
import tempfile
import time

import psycopg

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.probe_embedding_profile import dotenv_value
from services.embedding import IsaacusEmbeddingClient
from services.evaluation.gold import gold_sha256, load_cases
from services.evaluation.retrieval import RetrievalBenchmark
from services.retrieval import HybridRetriever, RetrievalSettings, SearchStore


DEFAULT_DSN = "postgresql://fintaxgpt:fintaxgpt-local-only@127.0.0.1:5433/fintaxgpt"
DEFAULT_GOLD = ROOT / "evals/australia_tax_legal_gold.jsonl"
DEFAULT_CACHE = ROOT / "data/embeddings/kanon2-768-v1/benchmark_query_vectors.json"
DEFAULT_OUTPUT = ROOT / "data/evaluations/phase3_retrieval_baseline.json"


def _write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            json.dump(value, handle, indent=2, sort_keys=True)
            handle.write("\n")
        os.replace(temporary, path)
    except BaseException:
        Path(temporary).unlink(missing_ok=True)
        raise


def _percentile(values: list[float], percent: float) -> float:
    ordered = sorted(values)
    index = min(len(ordered) - 1, round((len(ordered) - 1) * percent))
    return ordered[index]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dsn", default=os.environ.get("FINTAX_DATABASE_URL", DEFAULT_DSN))
    parser.add_argument("--env", type=Path, default=ROOT / ".env")
    parser.add_argument("--gold", type=Path, default=DEFAULT_GOLD)
    parser.add_argument("--cache", type=Path, default=DEFAULT_CACHE)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--limit", type=int, default=100)
    args = parser.parse_args()
    cases = load_cases(args.gold)
    cache = json.loads(args.cache.read_text()) if args.cache.exists() else {}
    client = IsaacusEmbeddingClient(dotenv_value(args.env, "ISAACUS_API_KEY"))
    dirty = 0

    def embed(query: str) -> tuple[float, ...]:
        nonlocal dirty
        key = hashlib.sha256(query.encode()).hexdigest()
        if key not in cache:
            cache[key] = list(client.embed_query(query))
            dirty += 1
            if dirty % 10 == 0:
                _write_json(args.cache, cache)
        return tuple(cache[key])

    benchmark = RetrievalBenchmark()
    latencies: list[float] = []
    failures: list[dict] = []
    with psycopg.connect(args.dsn) as connection:
        retriever = HybridRetriever(SearchStore(connection))
        for number, case in enumerate(cases, start=1):
            started = time.perf_counter()
            result = retriever.search(case["question"], embed, args.limit)
            latencies.append((time.perf_counter() - started) * 1000)
            rank = benchmark.add(case, result)
            if rank is None:
                failures.append({"id": case["id"], "route": result.route})
            if number == 1 or number % 25 == 0:
                print(json.dumps({"processed": number, "failures": len(failures)}), flush=True)
    if dirty:
        _write_json(args.cache, cache)
    report = benchmark.report()
    report.update({
        "schema_version": "fintax-phase3-retrieval-eval-1.0",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "gold_sha256": gold_sha256(args.gold),
        "settings_version": RetrievalSettings().version,
        "new_query_embeddings": dirty,
        "latency_ms": {"mean": statistics.fmean(latencies),
                       "p50": _percentile(latencies, 0.50),
                       "p95": _percentile(latencies, 0.95)},
        "failures": failures,
    })
    _write_json(args.output, report)
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
