"""Tests for Phase 7 staging-baseline classification and organic feedback capture."""

import json

from packages.telemetry import get_global_collector, span, trace_context
from services.evaluation import (
    StagingQueryRecord,
    StagingUserFeedback,
    classify_acceptance,
    load_staging_records,
    log_staging_record,
    summarize_staging_trial,
)


def _record() -> StagingQueryRecord:
    return StagingQueryRecord(
        query_id="organic-1",
        query="Is this deduction available?",
        timestamp="2026-09-28T10:00:00+00:00",
        final_decision="inadequate-evidence",
        corpus_scope_reason="IN_SCOPE_TAX_CORPUS",
        evidence_adequacy_reason="Marginal evidence support",
        retrieved_authorities=("ITAA 1997 s 8-1",),
        reranker_scores=(0.72,),
        generation_model="not-called",
        judge_decision={"evidence_support": 0.4},
        latency_ms=91.2,
        cost_usd=0.001,
        trace_id="staging-trace-1",
        user_feedback=StagingUserFeedback(
            user_id="practitioner-1",
            user_role="tax-agent",
            useful=False,
            abstention_assessment="unnecessarily-conservative",
            user_correction="The cited section was sufficient.",
            abstention_root_cause="coverage-threshold",
        ),
    )


def test_acceptance_separates_safety_from_usability():
    status, gates = classify_acceptance({
        "false_answer_rate": 0.0,
        "evaluation_kind": "independent_human_review",
        "cases_evaluated": 35, "claims_evaluated": 20,
        "unsupported_claim_rate": 0.0, "authority_correctness": 1.0,
        "locator_correctness": 1.0,
        "version_as_of_correctness": 1.0,
        "false_abstention_rate": 0.15,
    })
    assert status == "safe_for_staging"
    assert gates["safety_gate"] == "passed"
    assert gates["usability_gate"] == "target_not_yet_met"
    assert gates["staging_authorized"] is True
    assert gates["broad_production_authorized"] is False

    _, passing_gates = classify_acceptance({
        "false_answer_rate": 0.0,
        "evaluation_kind": "independent_human_review",
        "cases_evaluated": 35, "claims_evaluated": 20,
        "unsupported_claim_rate": 0.0, "authority_correctness": 1.0,
        "locator_correctness": 1.0,
        "version_as_of_correctness": 1.0,
        "false_abstention_rate": 0.0,
    })
    assert passing_gates["broad_production_authorized"] is False


def test_staging_record_is_logged_and_attached_to_trace(tmp_path):
    collector = get_global_collector()
    collector.clear()
    output = tmp_path / "staging.jsonl"
    with trace_context(trace_id="staging-trace-1"):
        with span("staging_query"):
            log_staging_record(_record(), output)

    payload = json.loads(output.read_text())
    assert payload["final_decision"] == "inadequate-evidence"
    root = collector.get_spans()[0]
    assert root.attributes["trial.label"] == "staging / not formal professional validation"
    assert root.attributes["feedback.abstention_assessment"] == "unnecessarily-conservative"

    summary = summarize_staging_trial(load_staging_records(output))
    assert summary["conservative_abstentions_count"] == 1
    assert summary["abstention_root_causes"] == {"coverage-threshold": 1}


def test_structural_historical_metrics_cannot_authorize_staging():
    status, gates = classify_acceptance({
        "false_answer_rate": 0.0, "citation_correctness_rate": 1.0,
        "source_version_correctness_rate": 1.0, "false_abstention_rate": 0.0,
    })
    assert status == "acceptance_failed"
    assert not gates["staging_authorized"]
