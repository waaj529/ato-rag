#!/usr/bin/env python3
"""Capture channel-level evidence for every frozen Phase 3 top-100 miss."""

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import sys
import tempfile

import psycopg

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from services.evaluation.gold import gold_sha256, load_cases
from services.evaluation.retrieval_diagnostics import diagnose_case


DEFAULT_DSN = "postgresql://fintaxgpt:fintaxgpt-local-only@127.0.0.1:5433/fintaxgpt"
BASELINE = ROOT / "data/evaluations/phase3_retrieval_baseline.json"
GOLD = ROOT / "evals/australia_tax_legal_gold.jsonl"
CACHE = ROOT / "data/embeddings/kanon2-768-v1/benchmark_query_vectors.json"
OUTPUT = ROOT / "data/evaluations/phase3_retrieval_failure_evidence.json"


def _write(path: Path, value: object) -> None:
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


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dsn", default=os.environ.get("FINTAX_DATABASE_URL", DEFAULT_DSN))
    parser.add_argument("--baseline", type=Path, default=BASELINE)
    parser.add_argument("--gold", type=Path, default=GOLD)
    parser.add_argument("--cache", type=Path, default=CACHE)
    parser.add_argument("--output", type=Path, default=OUTPUT)
    args = parser.parse_args()
    baseline = json.loads(args.baseline.read_text())
    settings_version = str(baseline.get("settings_version") or "")
    if not settings_version.startswith("phase3-rrf-v"):
        raise ValueError("analysis requires a frozen Phase 3 RRF benchmark")
    cases = {case["id"]: case for case in load_cases(args.gold)}
    cache = json.loads(args.cache.read_text())
    failures = [item["id"] for item in baseline["failures"]]
    records = []
    with psycopg.connect(args.dsn) as connection:
        for number, case_id in enumerate(failures, 1):
            case = cases[case_id]
            key = hashlib.sha256(case["question"].encode()).hexdigest()
            records.append(diagnose_case(connection, case, tuple(cache[key])))
            print(json.dumps({"processed": number, "case_id": case_id}), flush=True)
    report = {
        "schema_version": "fintax-phase3-retrieval-failure-evidence-1.0",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "baseline_settings_version": baseline["settings_version"],
        "gold_sha256": gold_sha256(args.gold), "case_count": len(records),
        "cases": records,
    }
    _write(args.output, report)
    print(json.dumps({"output": str(args.output), "case_count": len(records)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
