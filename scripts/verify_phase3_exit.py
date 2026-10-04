#!/usr/bin/env python3
"""Verify the immutable Phase 3 retrieval baseline and measured exit gate."""

from dataclasses import asdict
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from services.retrieval import RetrievalSettings


LOCK = ROOT / "data/evaluations/phase3_baseline_lock.json"


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def verify_phase3_exit(lock_path: Path = LOCK) -> dict:
    lock = json.loads(lock_path.read_text())
    benchmark_path = ROOT / lock["benchmark_report"]
    analysis_path = ROOT / lock["failure_analysis"]
    benchmark = json.loads(benchmark_path.read_text())
    analysis = json.loads(analysis_path.read_text())
    failures = []
    if _sha256(benchmark_path) != lock["benchmark_report_sha256"]:
        failures.append("benchmark report hash changed")
    if _sha256(analysis_path) != lock["failure_analysis_sha256"]:
        failures.append("failure analysis hash changed")
    settings = asdict(RetrievalSettings())
    expected = {**lock["retrieval_settings"], "version": lock["settings_version"]}
    if settings != expected:
        failures.append("Phase 3 retrieval settings changed after freeze")
    if benchmark.get("gold_sha256") != lock["benchmark_sha256"]:
        failures.append("benchmark SHA does not match the frozen baseline")
    gate = lock["exit_gate"]
    measured = {
        "recall_at_100": benchmark["overall"]["recall_at_100"],
        "recall_at_60": benchmark["overall"]["recall_at_60"],
        "recall_at_20": benchmark["overall"]["recall_at_20"],
        "abstention_accuracy": benchmark["abstention_accuracy"],
        "median_latency_ms": benchmark["latency_ms"]["p50"],
        "p95_latency_ms": benchmark["latency_ms"]["p95"],
    }
    for cutoff in (100, 60, 20):
        if measured[f"recall_at_{cutoff}"] < gate[f"recall_at_{cutoff}_minimum"]:
            failures.append(f"Recall@{cutoff} is below the frozen exit gate")
    if measured["abstention_accuracy"] != gate["abstention_accuracy_required"]:
        failures.append("abstention accuracy is below the frozen exit gate")
    if measured["median_latency_ms"] >= gate["median_latency_ms_maximum"]:
        failures.append("median latency exceeds the frozen exit gate")
    if measured["p95_latency_ms"] >= gate["p95_latency_ms_maximum"]:
        failures.append("p95 latency exceeds the frozen exit gate")
    aggregate = analysis.get("aggregate") or {}
    for failure_class in gate["systemic_defect_classes_required_zero"]:
        if aggregate.get(failure_class, 0):
            failures.append(f"unresolved systemic failure class: {failure_class}")
    if analysis.get("case_count") != len(benchmark.get("failures") or []):
        failures.append("remaining misses are not fully analyzed")
    return {
        "schema_version": "fintax-phase3-exit-verification-1.0",
        "passed": not failures, "status": lock["status"],
        "settings_version": lock["settings_version"],
        "benchmark_sha256": lock["benchmark_sha256"],
        "measured": measured, "failures": failures,
    }


def main() -> int:
    report = verify_phase3_exit()
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
