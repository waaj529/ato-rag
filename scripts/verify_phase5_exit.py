#!/usr/bin/env python3
"""Verify the immutable Phase 5 generation and citation baseline lock."""

import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

LOCK = ROOT / "data/evaluations/phase5_baseline_lock.json"


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def verify_phase5_exit(lock_path: Path = LOCK) -> dict:
    lock = json.loads(lock_path.read_text())
    benchmark_path = ROOT / lock["benchmark_report"]
    benchmark = json.loads(benchmark_path.read_text())
    failures = []

    if _sha256(benchmark_path) != lock["benchmark_report_sha256"]:
        failures.append("Phase 5 benchmark report hash changed")
    if benchmark.get("gold_sha256") != lock["benchmark_sha256"]:
        failures.append("Phase 5 gold set SHA mismatch")

    gate = lock["exit_gate"]
    metrics = benchmark.get("metrics") or {}

    checks = [
        ("citation_resolvability_rate", metrics.get("citation_resolvability_rate", 0), gate["citation_resolvability_rate_minimum"], ">="),
        ("material_claim_citation_support_rate", metrics.get("material_claim_citation_support_rate", 0), gate["material_claim_citation_support_rate_minimum"], ">="),
        ("unsupported_claim_rate", metrics.get("unsupported_claim_rate", 1), gate["unsupported_claim_rate_maximum"], "<="),
        ("correct_jurisdiction_version_rate", metrics.get("correct_jurisdiction_version_rate", 0), gate["correct_jurisdiction_version_rate_minimum"], ">="),
        ("abstention_correctness", metrics.get("abstention_correctness", 0), gate["abstention_correctness_required"], "=="),
        ("mean_answer_completeness", metrics.get("mean_answer_completeness", 0), gate["mean_answer_completeness_minimum"], ">="),
        ("mean_evidence_support", metrics.get("mean_evidence_support", 0), gate["mean_evidence_support_minimum"], ">="),
        ("mean_jev_judge_score", metrics.get("mean_jev_judge_score", 0), gate["mean_jev_judge_score_minimum"], ">="),
        ("repair_invocation_rate", metrics.get("repair_invocation_rate", 1), gate["repair_invocation_rate_maximum"], "<="),
    ]

    for name, val, threshold, op in checks:
        if op == ">=" and val < threshold:
            failures.append(f"{name} {val} is below required minimum {threshold}")
        elif op == "<=" and val > threshold:
            failures.append(f"{name} {val} exceeds allowed maximum {threshold}")
        elif op == "==" and val != threshold:
            failures.append(f"{name} {val} does not match required {threshold}")

    return {
        "schema_version": "fintax-phase5-exit-verification-1.0",
        "passed": False,
        "historical_artifact_valid": not failures,
        "status": "historical_only_current_phase5_blocked",
        "measured": metrics,
        "failures": failures + ["Historical proxy metrics do not validate current production generation"],
    }


def main() -> int:
    report = verify_phase5_exit()
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
