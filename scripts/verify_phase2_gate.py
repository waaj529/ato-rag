#!/usr/bin/env python3
"""Fail-closed verification of Phase 0/2 prerequisites for Phase 3."""

import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from services.chunker.validation import SourceResolver
from services.evaluation.approval import (
    approval_failures, governance_failures, load_review_record,
)
from services.evaluation.gold import load_cases, validate_gold_set
from services.evaluation.phase2 import golden_fixture_failures

GOLD = ROOT / "evals/australia_tax_legal_gold.jsonl"
APPROVAL = ROOT / "evals/domain_review_approval.json"
GOLDEN = ROOT / "evals/phase2/golden_ready_document_chunker.jsonl"
IMPORTS = (ROOT / "data/imports/ato_ready.json", ROOT / "data/imports/court_ready.json")
COURT_ATTEMPT = ROOT / "data/imports/court_ready_attempt.json"
TECHNICAL_CHECKS = (
    "benchmark_candidates_300_source_exact_answer_bearing",
    "golden_ready_document_chunker",
    "official_court_decision_coverage",
)


def _court_coverage_failures(resolver: SourceResolver) -> list[str]:
    positive_cases = [
        case for case in load_cases(GOLD)
        if not case["must_abstain"] and any(
            resolver.has_document(document_id)
            and (resolver.document(document_id).get("classification") or {}).get("source_class")
            == "court_decision"
            for document_id in case["expected_documents"]
        )
    ]
    if positive_cases:
        return []
    if COURT_ATTEMPT.is_file():
        attempt = json.loads(COURT_ATTEMPT.read_text())
        return [
            f"official court ingestion produced {attempt.get('document_count', 0)} of "
            f"{attempt.get('attempted', 0)} seeded judgments; "
            f"{attempt.get('skipped', 0)} failed (see {COURT_ATTEMPT.relative_to(ROOT)})"
        ]
    return [
        "no positive court-decision case backed by an official court source; "
        "the architecture's P0 corpus requirement is unmet"
    ]


def _gate_report(checks: dict[str, dict]) -> dict:
    for check in checks.values():
        check["passed"] = not check["failures"]
    technical_passed = all(checks[name]["passed"] for name in TECHNICAL_CHECKS)
    governance_valid = checks["domain_review_governance"]["passed"]
    domain_approved = checks["qualified_professional_review"]["passed"]
    review_status = checks["domain_review_governance"].get("status")
    progression_authorized = technical_passed and governance_valid
    if domain_approved:
        authorization_basis = "qualified_professional_approval"
        benchmark_status = "professionally_approved"
    elif review_status == "waived" and governance_valid:
        authorization_basis = "project_owner_waiver"
        benchmark_status = "waived_not_performed"
    else:
        authorization_basis = "unauthorized_review_governance"
        benchmark_status = "unreviewed"
    return {
        "schema_version": "fintax-phase2-gate-1.2",
        "phase2_chunking_gate_passed": technical_passed,
        "engineering_phase_progression_authorized": progression_authorized,
        "phase3_retrieval_authorized": progression_authorized,
        "phase3_authorization_basis": authorization_basis,
        "benchmark_review_status": benchmark_status,
        "qualified_professional_review_performed": domain_approved,
        "professional_pilot_authorized": technical_passed and domain_approved,
        "checks": checks,
    }


def main() -> int:
    resolver = SourceResolver(IMPORTS)
    gold = validate_gold_set(GOLD, resolver)
    review_record = load_review_record(APPROVAL)
    checks = {
        "benchmark_candidates_300_source_exact_answer_bearing": {
            "passed": gold.valid, "case_count": gold.count, "failures": gold.failures,
        },
        "golden_ready_document_chunker": {
            "passed": True, "failures": golden_fixture_failures(GOLDEN, IMPORTS),
        },
        "official_court_decision_coverage": {
            "passed": True, "failures": _court_coverage_failures(resolver),
        },
        "domain_review_governance": {
            "passed": True, "status": review_record.get("status"),
            "failures": governance_failures(GOLD, APPROVAL),
        },
        "qualified_professional_review": {
            "passed": True, "failures": approval_failures(GOLD, APPROVAL),
        },
    }
    report = _gate_report(checks)
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["phase3_retrieval_authorized"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
