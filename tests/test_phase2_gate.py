"""Technical and professional authorization remain separate."""

import json

import scripts.verify_phase2_gate as gate
from scripts.verify_phase2_gate import TECHNICAL_CHECKS, _gate_report


def test_project_owner_waiver_authorizes_engineering_not_professional_pilot():
    checks = {name: {"failures": []} for name in TECHNICAL_CHECKS}
    checks["domain_review_governance"] = {"status": "waived", "failures": []}
    checks["qualified_professional_review"] = {
        "failures": ["qualified professional review was not performed"]
    }
    report = _gate_report(checks)
    assert report["phase2_chunking_gate_passed"] is True
    assert report["engineering_phase_progression_authorized"] is True
    assert report["phase3_retrieval_authorized"] is True
    assert report["phase3_authorization_basis"] == "project_owner_waiver"
    assert report["benchmark_review_status"] == "waived_not_performed"
    assert report["qualified_professional_review_performed"] is False
    assert report["professional_pilot_authorized"] is False


def test_unknown_court_document_produces_a_reportable_failure(tmp_path, monkeypatch):
    gold = tmp_path / "gold.jsonl"
    gold.write_text(json.dumps({
        "must_abstain": False,
        "expected_documents": ["missing-document"],
    }) + "\n")
    monkeypatch.setattr(gate, "GOLD", gold)
    monkeypatch.setattr(gate, "COURT_ATTEMPT", tmp_path / "missing-attempt.json")

    class Resolver:
        @staticmethod
        def has_document(document_id):
            return False

        @staticmethod
        def document(document_id):
            raise AssertionError("unknown documents must not be loaded")

    failures = gate._court_coverage_failures(Resolver())
    assert failures and "no positive court-decision case" in failures[0]
