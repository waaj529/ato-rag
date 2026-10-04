"""Phase 5 grounded generation and citation verification evaluation metrics."""

import statistics
from typing import Sequence

from services.verification import PipelineResponse


def summarize_generation_benchmark(
    cases: Sequence[dict], responses: Sequence[PipelineResponse]
) -> dict:
    if len(cases) != len(responses):
        raise ValueError("Every case must have one response")
    total = len(cases)
    if total == 0:
        return {}

    resolvable_cits = 0
    total_cits = 0
    supported_claims = 0
    total_claims = 0
    unsupported_claims = 0
    jurisdiction_valid = 0
    repairs = 0
    completeness_scores: list[float] = []
    support_scores: list[float] = []
    judge_scores: list[float] = []
    abstention_matches = 0
    abstention_cases = 0

    for case, resp in zip(cases, responses):
        must_abstain = bool(case.get("must_abstain"))
        if must_abstain:
            abstention_cases += 1
            if resp.abstained or not resp.answer.claims:
                abstention_matches += 1
        elif not resp.abstained and resp.answer.claims:
            abstention_matches += 1

        cits = resp.validation.resolved_citations
        cit_ids = {u.evidence_id for u in cits}
        total_cits += len(cits)
        for cit in cits:
            if cit.official_url and cit.document_id and cit.document_version_id and cit.locator:
                resolvable_cits += 1
            if cit.jurisdiction == "AU-COMMONWEALTH":
                jurisdiction_valid += 1

        claims = resp.answer.claims
        total_claims += len(claims)
        for claim in claims:
            if claim.evidence_ids and all(eid in cit_ids for eid in claim.evidence_ids):
                supported_claims += 1
            else:
                unsupported_claims += 1

        if resp.repaired:
            repairs += 1

        if resp.judge.evaluation_kind == "heuristic_proxy":
            completeness_scores.append(resp.judge.answer_completeness)
            support_scores.append(resp.judge.evidence_support)
            judge_scores.append(resp.judge.overall_score)

    cit_resolvability = resolvable_cits / max(1, total_cits)
    claim_support_rate = supported_claims / max(1, total_claims)
    unsupported_rate = unsupported_claims / max(1, total_claims)
    jurisdiction_rate = jurisdiction_valid / max(1, total_cits)
    abstention_acc = abstention_matches / max(1, total)
    repair_rate = repairs / max(1, total)

    return {
        "cases_evaluated": total,
        "evaluation_kind": "structural_regression_only",
        "factual_accuracy": None,
        "version_as_of_correctness": None,
        "citation_resolvability_rate": round(cit_resolvability, 4),
        "material_claim_citation_membership_rate": round(claim_support_rate, 4),
        "structural_uncited_claim_rate": round(unsupported_rate, 4),
        "citation_jurisdiction_label_rate": round(jurisdiction_rate, 4),
        "abstention_correctness": round(abstention_acc, 4),
        "heuristic_completeness_proxy": round(statistics.fmean(completeness_scores), 4) if completeness_scores else None,
        "heuristic_support_proxy": round(statistics.fmean(support_scores), 4) if support_scores else None,
        "heuristic_aggregate_proxy": round(statistics.fmean(judge_scores), 4) if judge_scores else None,
        "repair_invocation_rate": round(repair_rate, 4),
    }
