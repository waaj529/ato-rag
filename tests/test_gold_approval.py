"""Fail-closed domain-review approval contract tests."""

import hashlib
import json
from pathlib import Path

from services.evaluation.approval import approval_failures, governance_failures
from services.evaluation.gold import gold_sha256

ROOT = Path(__file__).resolve().parents[1]


def test_missing_or_pending_governance_fails(tmp_path):
    gold = tmp_path / "gold.jsonl"
    gold.write_text("{}\n")
    approval = tmp_path / "approval.json"
    assert governance_failures(gold, approval) == ["domain-review governance record is missing"]
    approval.write_text(json.dumps({"status": "pending"}))
    failures = governance_failures(gold, approval)
    assert "domain review status must be approved or waived" in failures


def test_complete_hash_bound_approval_passes(tmp_path):
    gold = tmp_path / "gold.jsonl"
    gold.write_text("{}\n")
    approval = tmp_path / "approval.json"
    approval.write_text(json.dumps({
        "schema_version": "fintax-domain-review-governance-1.0",
        "status": "approved",
        "gold_sha256": hashlib.sha256(gold.read_bytes()).hexdigest(),
        "reviewer_name": "Qualified Reviewer",
        "reviewer_qualification": "Australian tax domain reviewer",
        "approved_at": "2026-09-21T00:00:00+00:00",
    }))
    assert approval_failures(gold, approval) == []
    assert governance_failures(gold, approval) == []


def test_hash_bound_project_owner_waiver_allows_governance_not_approval(tmp_path):
    gold = tmp_path / "gold.jsonl"
    gold.write_text("{}\n")
    waiver = tmp_path / "approval.json"
    waiver.write_text(json.dumps({
        "schema_version": "fintax-domain-review-governance-1.0",
        "status": "waived",
        "gold_sha256": hashlib.sha256(gold.read_bytes()).hexdigest(),
        "waiver_authority": "project_owner",
        "waiver_reason": "Qualified reviewer unavailable; review deferred.",
        "waived_at": "2026-09-26T11:06:24+05:00",
        "architecture_revision": "2026-09-26-domain-review-waiver-1",
    }))
    assert governance_failures(gold, waiver) == []
    assert approval_failures(gold, waiver) == [
        "qualified professional review was not performed"
    ]


def test_schema_version_mismatch_fails(tmp_path):
    gold = tmp_path / "gold.jsonl"
    gold.write_text("{}\n")
    approval = tmp_path / "approval.json"
    approval.write_text(json.dumps({
        "schema_version": "fintax-domain-review-governance-0.9",
        "status": "approved",
        "gold_sha256": hashlib.sha256(gold.read_bytes()).hexdigest(),
        "reviewer_name": "Qualified Reviewer",
        "reviewer_qualification": "Australian tax domain reviewer",
        "approved_at": "2026-09-21T00:00:00+00:00",
    }))
    failures = approval_failures(gold, approval)
    assert "review schema_version must be fintax-domain-review-governance-1.0" in failures


def test_shipped_approval_record_is_bound_to_the_current_gold_set():
    gold = ROOT / "evals/australia_tax_legal_gold.jsonl"
    record = json.loads((ROOT / "evals/domain_review_approval.json").read_text())
    assert record["gold_sha256"] == gold_sha256(gold)
