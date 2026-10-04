"""Regression tests for fail-closed generated answers and evidence lineage."""

from dataclasses import replace

import pytest

from services.context_builder import ContextPackage, EvidenceUnit
from services.generation import Claim, ModelRouter, StructuredAnswer
from services.verification import DeterministicValidator, GroundedAnswerPipeline


def _context():
    evidence = EvidenceUnit(
        evidence_id="E1", parent_id="p1", document_id="doc1", version_id="v1",
        authority_class="legislation", citation_label="Tax Act", title="Tax Act",
        source_url="https://www.ato.gov.au/example", heading_path=(),
        parent_locator={"section_id": "8-1"}, triggering_child_locator={},
        retrieval_reason="exact+dense", reranker_score=0.95,
        text="Expenses incurred in producing income may be deductible.", text_units=10,
    )
    return ContextPackage("expenses", (evidence,), 10, "test")


def _answer(evidence_ids=("E1",)):
    return StructuredAnswer("Claim text", (Claim("C1", "Claim text", evidence_ids),), (), False)


@pytest.mark.parametrize("evidence_ids", [("E99",), ("E1", "E99"), ()])
def test_repair_never_launders_invalid_citations(evidence_ids):
    class InvalidGenerator:
        model_name = "test"
        provider_name = "test"
        revision = "test"

        def generate_answer(self, query, context, task="generate"):
            return _answer(evidence_ids), 1, 1

    response = GroundedAnswerPipeline(router=ModelRouter(InvalidGenerator())).run("expenses", _context())
    assert response.abstained
    assert response.decision_reason == "VALIDATION_FAILED"
    assert not response.answer.claims
    assert "Claim text" not in response.answer.answer_markdown


def test_claimless_prose_cannot_pass_as_verified_answer():
    result = DeterministicValidator().validate(replace(_answer(), claims=()), _context())
    assert not result.passed


@pytest.mark.parametrize("field", ["source_url", "parent_id", "document_id", "version_id"])
def test_missing_evidence_lineage_is_rejected(field):
    context = _context()
    evidence = replace(context.evidence[0], **{field: ""})
    result = DeterministicValidator().validate(_answer(), replace(context, evidence=(evidence,)))
    assert not result.passed


def test_duplicate_evidence_ids_are_ambiguous():
    context = _context()
    duplicate = replace(context.evidence[0], document_id="different-document")
    result = DeterministicValidator().validate(
        _answer(), replace(context, evidence=context.evidence + (duplicate,)),
    )
    assert not result.passed


def test_duplicate_claim_ids_are_rejected():
    answer = _answer()
    result = DeterministicValidator().validate(replace(answer, claims=answer.claims * 2), _context())
    assert not result.passed
