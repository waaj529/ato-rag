"""Unit tests for Phase 5 grounded generation and model routing."""

from packages.telemetry import get_global_collector
from services.context_builder import ContextPackage, EvidenceUnit
from services.generation import (
    Claim,
    ExtractiveGenerator,
    ModelRouter,
    RepairGenerator,
    StructuredAnswer,
    format_generation_prompt,
)


def _evidence(eid: str, label: str, text: str) -> EvidenceUnit:
    return EvidenceUnit(
        evidence_id=eid, parent_id=f"p_{eid}", document_id="doc_1", version_id="v_1",
        authority_class="legislation", citation_label=label, title="Tax Act",
        source_url="https://ato.gov.au/doc1", heading_path=("Tax Act",),
        parent_locator={"section_id": "8-1"}, triggering_child_locator={"section_id": "8-1"},
        retrieval_reason="exact+dense", reranker_score=0.92, text=text, text_units=50,
    )


def test_grounded_generator_produces_structured_claims():
    ev = (_evidence("E1", "ITAA 1997 s 8-1", "A taxpayer may deduct from assessable income any loss or outgoing incurred in gaining or producing assessable income."),)
    pkg = ContextPackage(query="deductible expenses", evidence=ev, total_text_units=50, settings_version="v1")
    gen = ExtractiveGenerator()
    ans, in_tok, out_tok = gen.generate_answer("deductible expenses", pkg)

    assert len(ans.claims) == 1
    assert ans.claims[0].claim_id == "C1"
    assert ans.claims[0].evidence_ids == ("E1",)
    assert "ITAA 1997 s 8-1" in ans.answer_markdown
    assert not ans.needs_human_review


def test_grounded_generator_abstains_when_evidence_empty():
    pkg = ContextPackage(query="unanswerable query", evidence=(), total_text_units=0, settings_version="v1")
    ans, _, _ = ExtractiveGenerator().generate_answer("unanswerable query", pkg)
    assert len(ans.claims) == 0
    assert "insufficient authoritative evidence" in ans.answer_markdown.lower()
    assert ans.needs_human_review is True


def test_repair_generator_preserves_unresolved_evidence_for_rejection():
    ev = (_evidence("E1", "ITAA 1997 s 8-1", "Text of s 8-1"),)
    pkg = ContextPackage(query="query", evidence=ev, total_text_units=50, settings_version="v1")
    draft = StructuredAnswer(
        answer_markdown="Markdown",
        claims=(Claim("C1", "Statement", ("E99",)),),
        limitations=(),
        needs_human_review=False,
    )
    repairer = RepairGenerator()
    repaired = repairer.repair(draft, ["Unsupplied ID E99"], pkg)
    assert repaired.claims[0].evidence_ids == ("E99",)
    assert repaired.needs_human_review
    assert "Unresolved validation error" in repaired.limitations[0]


def test_explicit_extractive_fixture_is_not_a_model_call():
    collector = get_global_collector()
    collector.clear()
    ev = (_evidence("E1", "TR 2026/1", "Taxation ruling on deductions"),)
    pkg = ContextPackage(query="query", evidence=ev, total_text_units=50, settings_version="v1")
    router = ModelRouter(ExtractiveGenerator())
    ans = router.generate("query", pkg)
    assert ans.claims

    assert collector.get_observations() == []
