"""Independent labels detect errors that mere citation membership cannot detect."""

from dataclasses import asdict, replace

import pytest

from services.evaluation import AnswerReview, ReviewedCase, evidence_hash, evaluate_review
from services.generation import Claim, StructuredAnswer
from services.verification import CitationObject, EvidenceState, JudgeDecision, PipelineResponse, ValidationResult


def _inputs(entailed=True, version="v1", as_of="2026-01-01"):
    case = ReviewedCase.model_validate({
        "case_id": "independent-1", "question": "Are private expenses deductible?", "as_of": as_of,
        "must_abstain": False, "reviewer_id": "gold-reviewer", "propositions": [{
            "proposition_id": "P1", "text": "Private expenses are excluded.", "sources": [{
                "document_id": "doc1", "version_id": "v1", "official_url": "https://official.example/source",
                "locator": {"section_id": "8-1"}, "valid_from": "2020-01-01", "valid_to": "2026-06-30",
            }],
        }],
    })
    citation = CitationObject("cit1", "doc1", version, "E1", "Tax Act", "AU-COMMONWEALTH",
                              {"section_id": "8-1"}, "https://official.example/source", "/snapshot")
    answer = StructuredAnswer("Private expenses are deductible.", (Claim("C1", "Private expenses are deductible.", ("E1",)),), (), False)
    response = PipelineResponse(case.question, answer,
                                ValidationResult(True, (), EvidenceState.SUPPORTED, (citation,)),
                                JudgeDecision(1, 1, 1, 0), False, False)
    review = AnswerReview.model_validate({
        "case_sha256": evidence_hash(case.model_dump(mode="json")), "response_sha256": evidence_hash(asdict(response)),
        "reviewer_id": "independent-reviewer", "method": "independent_human_review",
        "all_material_claims_enumerated": True,
        "claims": [{"claim_id": "C1", "proposition_id": "P1", "entailed_by_cited_evidence": entailed}],
    })
    return case, response, review


def test_valid_citation_does_not_make_false_claim_supported():
    metrics = evaluate_review(*_inputs(entailed=False))
    assert metrics["authority_correctness"] == 1
    assert metrics["claim_entailment_rate"] == 0
    assert metrics["unsupported_claim_rate"] == 1
    assert metrics["proposition_completeness"] == 0


@pytest.mark.parametrize("kwargs", [{"version": "v2"}, {"as_of": "2027-01-01"}])
def test_wrong_version_or_date_fails_even_with_positive_entailment_label(kwargs):
    metrics = evaluate_review(*_inputs(**kwargs))
    assert metrics["claim_entailment_rate"] == 1
    assert metrics["version_as_of_correctness"] == 0
    assert metrics["unsupported_claim_rate"] == 1


def test_stale_review_cannot_validate_changed_answer():
    case, response, review = _inputs()
    response = replace(response, answer=replace(response.answer, answer_markdown="Changed claim"))
    with pytest.raises(ValueError, match="exact answer"):
        evaluate_review(case, response, review)


def test_missing_claim_labels_and_unenumerated_prose_fail_closed():
    case, response, review = _inputs()
    with pytest.raises(ValueError, match="exactly one"):
        evaluate_review(case, response, review.model_copy(update={"claims": []}))
    with pytest.raises(ValueError, match="Unenumerated"):
        evaluate_review(case, response, review.model_copy(update={"all_material_claims_enumerated": False}))
