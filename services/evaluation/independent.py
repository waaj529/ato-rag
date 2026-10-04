"""Evaluate independent claim reviews against source/version/as-of gold evidence."""

from dataclasses import asdict
import hashlib
import json

from .review_models import AnswerReview, ReviewedCase


def evidence_hash(value) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), default=str).encode()).hexdigest()


def evaluate_review(case: ReviewedCase, response, review: AnswerReview) -> dict:
    if review.case_sha256 != evidence_hash(case.model_dump(mode="json")):
        raise ValueError("Review does not match the independent gold case")
    if review.response_sha256 != evidence_hash(asdict(response)):
        raise ValueError("Review does not match this exact answer and citations")
    if response.query != case.question:
        raise ValueError("Response question does not match the gold case")
    claims = {c.claim_id: c for c in response.answer.claims}
    labels = {c.claim_id: c for c in review.claims}
    if len(claims) != len(response.answer.claims) or len(labels) != len(review.claims) or claims.keys() != labels.keys():
        raise ValueError("Every material claim requires exactly one independent label")
    if not review.all_material_claims_enumerated:
        raise ValueError("Unenumerated prose cannot receive a complete accuracy grade")
    if response.abstained == bool(claims):
        raise ValueError("Abstention flag and material claims are inconsistent")
    propositions = {p.proposition_id: p for p in case.propositions}
    citations = {c.evidence_id: c for c in response.validation.resolved_citations}
    checks, covered = [], set()
    for cid, claim in claims.items():
        label = labels[cid]
        if label.proposition_id is not None and label.proposition_id not in propositions:
            raise ValueError("Review references unknown expected proposition")
        proposition = propositions.get(label.proposition_id)
        sources = proposition.sources if proposition else []
        source_checks = []
        for eid in claim.evidence_ids:
            citation = citations.get(eid)
            authority = [s for s in sources if citation and s.document_id == citation.document_id
                         and s.official_url == citation.official_url]
            version = [s for s in authority if s.version_id == citation.document_version_id
                       and s.valid_from <= case.as_of and (s.valid_to is None or case.as_of <= s.valid_to)]
            located = [s for s in version if all(citation.locator.get(k) == v for k, v in s.locator.items())]
            source_checks.append((bool(authority), bool(version), bool(located)))
        authority_ok = bool(source_checks) and all(x[0] for x in source_checks)
        version_ok = bool(source_checks) and all(x[1] for x in source_checks)
        locator_ok = bool(source_checks) and all(x[2] for x in source_checks)
        supported = label.entailed_by_cited_evidence and authority_ok and version_ok and locator_ok
        if supported:
            covered.add(label.proposition_id)
        checks.append({"claim_id": cid, "entailed": label.entailed_by_cited_evidence,
                       "authority_correct": authority_ok, "version_correct": version_ok,
                       "locator_correct": locator_ok, "supported": supported})
    rate = lambda key: sum(c[key] for c in checks) / len(checks) if checks else None
    abstained = response.abstained and not claims
    return {
        "must_abstain": case.must_abstain, "abstained": abstained,
        "case_id": case.case_id, "evaluation_kind": "independent_human_review",
        "claim_count": len(checks), "claims": checks,
        "claim_entailment_rate": rate("entailed"), "authority_correctness": rate("authority_correct"),
        "version_as_of_correctness": rate("version_correct"), "locator_correctness": rate("locator_correct"),
        "unsupported_claim_rate": 1-rate("supported") if checks else None,
        "proposition_completeness": len(covered)/len(propositions) if propositions else None,
        "abstention_correct": abstained == case.must_abstain and (abstained or bool(claims)),
        "broad_production_authorized": False,
    }
