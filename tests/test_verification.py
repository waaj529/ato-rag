"""Unit tests for Phase 5 citation resolution, deterministic validation and Jev judge."""

from packages.telemetry import get_global_collector
from services.context_builder import ContextPackage, EvidenceUnit
from services.generation import Claim, StructuredAnswer, ModelRouter, ExtractiveGenerator
from services.verification import (
    CitationResolver,
    DeterministicValidator,
    EvidenceState,
    GroundedAnswerPipeline,
    HeuristicEvidenceJudge,
)


def _ev(eid: str) -> EvidenceUnit:
    return EvidenceUnit(
        evidence_id=eid, parent_id=f"p_{eid}", document_id="doc_1", version_id="v_1",
        authority_class="legislation", citation_label="ITAA 1997 s 8-1", title="Tax Act",
        source_url="https://ato.gov.au/doc1", heading_path=("Tax Act",),
        parent_locator={"section_id": "8-1"}, triggering_child_locator={"section_id": "8-1"},
        retrieval_reason="exact+dense", reranker_score=0.95,
        text="A taxpayer may deduct losses and outgoings incurred in producing income.", text_units=50,
    )


def test_citation_resolver_builds_deterministic_citations():
    pkg = ContextPackage(query="q", evidence=(_ev("E1"),), total_text_units=50, settings_version="v1")
    resolver = CitationResolver()
    cits = resolver.resolve(["E1"], pkg)
    assert len(cits) == 1
    assert cits[0].citation_id == "cit_01"
    assert cits[0].document_id == "doc_1"
    assert cits[0].display == "ITAA 1997 s 8-1"
    assert cits[0].official_url == "https://ato.gov.au/doc1"


def test_deterministic_validator_detects_unsupplied_evidence():
    pkg = ContextPackage(query="q", evidence=(_ev("E1"),), total_text_units=50, settings_version="v1")
    val = DeterministicValidator()

    # Valid answer
    valid = StructuredAnswer(answer_markdown="Valid", claims=(Claim("C1", "Text", ("E1",)),), limitations=(), needs_human_review=False)
    res = val.validate(valid, pkg)
    assert res.passed
    assert res.evidence_state == EvidenceState.SUPPORTED

    # Invalid: unsupplied E99
    invalid = StructuredAnswer(answer_markdown="Invalid", claims=(Claim("C1", "Text", ("E99",)),), limitations=(), needs_human_review=False)
    bad_res = val.validate(invalid, pkg)
    assert not bad_res.passed
    assert any("E99" in err for err in bad_res.errors)


def test_heuristic_judge_is_not_reported_as_a_model_call():
    collector = get_global_collector()
    collector.clear()
    pkg = ContextPackage(query="deductions", evidence=(_ev("E1"),), total_text_units=50, settings_version="v1")
    ans = StructuredAnswer(answer_markdown="Deductions allowed under s 8-1", claims=(Claim("C1", "Deductions allowed", ("E1",)),), limitations=("Commonwealth jurisdiction",), needs_human_review=False)
    judge = HeuristicEvidenceJudge()
    decision = judge.judge("deductions", ans, pkg)

    assert decision.evidence_support > 0.7
    assert decision.answer_completeness > 0.8
    assert decision.overall_score > 0.7

    obs = collector.get_observations()
    assert obs == []
    assert decision.evaluation_kind == "heuristic_proxy"


def test_grounded_answer_pipeline_executes_end_to_end():
    pkg = ContextPackage(query="expenses", evidence=(_ev("E1"),), total_text_units=50, settings_version="v1")
    pipeline = GroundedAnswerPipeline(router=ModelRouter(ExtractiveGenerator()))
    res = pipeline.run("expenses", pkg)
    assert res.validation.passed
    assert not res.abstained
    assert len(res.validation.resolved_citations) >= 1
