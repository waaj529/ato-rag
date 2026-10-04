"""Tests for DeepEval evaluation adapters, metrics suite, and deferred telemetry."""

import os
from unittest.mock import MagicMock

import pytest

os.environ.setdefault("DEEPEVAL_TELEMETRY_OPT_OUT", "YES")

from deepeval.models.base_model import DeepEvalBaseLLM
from services.context_builder import ContextPackage, EvidenceUnit
from services.evaluation import (
    build_faithfulness_metric,
    build_rag_metric_suite,
    build_statutory_compliance_metric,
    create_llm_test_case,
    evaluate_test_case,
    pipeline_response_to_test_case,
    run_deepeval_suite,
)
from services.generation import Claim, StructuredAnswer
from services.verification import (
    EvidenceState,
    JudgeDecision,
    PipelineResponse,
    ValidationResult,
)


class DummyJudge(DeepEvalBaseLLM):
    def load_model(self):
        return self

    def generate(self, *args, **kwargs):
        return "1.0"

    async def a_generate(self, *args, **kwargs):
        return "1.0"

    def get_model_name(self):
        return "dummy-judge"


def test_create_llm_test_case_validation():
    tc = create_llm_test_case(
        query="What is assessable under s 6-5?",
        actual_output="Ordinary income is assessable.",
        retrieval_context=["s 6-5 ITAA97 covers ordinary income."],
        expected_output="Ordinary income under s 6-5.",
    )
    assert tc.input == "What is assessable under s 6-5?"
    assert tc.actual_output == "Ordinary income is assessable."
    assert len(tc.retrieval_context) == 1

    with pytest.raises(ValueError, match="Query cannot be empty"):
        create_llm_test_case("", "output", [])

    with pytest.raises(ValueError, match="Actual output cannot be empty"):
        create_llm_test_case("query", "", [])


def test_pipeline_response_to_test_case():
    response = PipelineResponse(
        query="Is interest deductible?",
        answer=StructuredAnswer(
            answer_markdown="Interest is deductible under s 8-1.",
            claims=(Claim("C1", "Interest deductible", ("E1",)),),
            limitations=(),
            needs_human_review=False,
        ),
        validation=ValidationResult(True, (), EvidenceState.SUPPORTED, ()),
        judge=JudgeDecision(0.95, 0.9, 0.9, 0.05),
        repaired=False,
        abstained=False,
    )
    unit = EvidenceUnit(
        evidence_id="E1",
        parent_id="P1",
        document_id="DOC1",
        version_id="V1",
        authority_class="primary",
        citation_label="s 8-1",
        title="ITAA97",
        source_url="https://ato.gov.au",
        heading_path=("General deductions",),
        parent_locator={},
        triggering_child_locator={},
        retrieval_reason="bm25",
        reranker_score=0.9,
        text="Interest incurred.",
        text_units=10,
    )
    context = ContextPackage(
        query="Is interest deductible?",
        evidence=(unit,),
        total_text_units=10,
        settings_version="phase4-context-v1",
    )

    tc = pipeline_response_to_test_case(response, context, expected_output="Deductible under s 8-1")
    assert tc.input == "Is interest deductible?"
    assert "Interest is deductible under s 8-1" in tc.actual_output
    assert len(tc.retrieval_context) == 1


def test_metric_builders_and_suite_construction():
    judge = DummyJudge()
    faith_m = build_faithfulness_metric(threshold=0.8, model=judge)
    assert faith_m.threshold == 0.8

    stat_m = build_statutory_compliance_metric(threshold=0.75, model=judge)
    assert stat_m.name == "Australian Statutory Compliance"
    assert stat_m.threshold == 0.75

    suite = build_rag_metric_suite(threshold=0.7, model=judge)
    assert len(suite) == 6


def test_run_deepeval_suite_execution():
    tc = create_llm_test_case("Test query", "Test answer", ["Test context"])
    mock_metric = MagicMock()
    mock_metric.__class__.__name__ = "MockFaithfulness"
    mock_metric.score = 0.9
    mock_metric.reason = "Faithful to context"
    mock_metric.is_successful.return_value = True

    single_result = evaluate_test_case(tc, [mock_metric])
    assert single_result["passed"] is True
    assert single_result["metrics"]["MockFaithfulness"]["score"] == 0.9

    suite_result = run_deepeval_suite([tc], [mock_metric])
    assert suite_result["total_cases"] == 1
    assert suite_result["all_passed"] is True
    assert "MockFaithfulness" in suite_result["metric_aggregates"]
    assert suite_result["metric_aggregates"]["MockFaithfulness"]["mean_score"] == 0.9
