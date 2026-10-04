"""Pilot evaluation metrics and user feedback structures (Phase 7)."""

from dataclasses import dataclass
import statistics
from typing import Sequence

from packages.telemetry import TraceCollector
from services.verification.pipeline import PipelineResponse


@dataclass(frozen=True)
class PilotFeedback:
    case_id: str
    tester_id: str
    usefulness_score: int  # 1 (poor) to 5 (excellent)
    user_correction: str | None = None
    manual_verification_required: bool = False


def simulate_pilot_feedback(case: dict, response: PipelineResponse) -> PilotFeedback:
    must_abstain = case.get("must_abstain", False)
    tid = case.get("tester_id", "T1")
    if must_abstain:
        if response.abstained:
            return PilotFeedback(case["id"], tid, 5, None, False)
        return PilotFeedback(case["id"], tid, 1, "Hallucinated answer on unanswerable query", True)
    if response.abstained:
        return PilotFeedback(case["id"], tid, 2, "Abstained unexpectedly on answerable query", True)
    score = 5 if len(response.answer.claims) >= 2 else 4
    correction = "Consider including specific paragraph pinpoints" if score == 4 else None
    return PilotFeedback(case["id"], tid, score, correction, False)


def compute_pilot_metrics(
    cases: list[dict],
    responses: list[PipelineResponse],
    feedbacks: list[PilotFeedback],
    latencies_ms: list[float],
    collector: TraceCollector,
) -> dict:
    if not (len(cases) == len(responses) == len(latencies_ms)):
        raise ValueError("Each case requires a response and latency")
    total = len(cases)
    if total == 0:
        return {}

    # Latencies
    sorted_latencies = sorted(latencies_ms)
    p50_lat = statistics.median(sorted_latencies)
    p95_lat = sorted_latencies[int(len(sorted_latencies) * 0.95)] if sorted_latencies else 0.0

    # User feedback metrics
    usefulness_avg = statistics.mean(fb.usefulness_score for fb in feedbacks) if feedbacks else 0.0
    corrections_submitted = [fb.user_correction for fb in feedbacks if fb.user_correction]
    manual_verif_count = sum(1 for fb in feedbacks if fb.manual_verification_required or fb.usefulness_score < 3)
    manual_verif_rate = manual_verif_count / total

    # Citations and verification metrics
    citation_ok = 0
    source_version_ok = 0
    abstention_correct = 0
    unanswerable_correct = 0
    unanswerable_count = 0
    retrieval_failures = 0

    for case, resp in zip(cases, responses):
        must_abstain = case.get("must_abstain", False)
        if must_abstain:
            unanswerable_count += 1
            if resp.abstained or len(resp.answer.claims) == 0:
                unanswerable_correct += 1
                abstention_correct += 1
        else:
            if not resp.abstained and len(resp.answer.claims) > 0:
                abstention_correct += 1
            else:
                retrieval_failures += 1

        if resp.validation.passed:
            citation_ok += 1
            source_version_ok += 1
        elif resp.abstained:
            citation_ok += 1
            source_version_ok += 1

    obs = collector.get_observations()
    total_cost = sum(o.cost or 0 for o in obs)
    provider_errors = sum(1 for o in obs if o.status != "ok")
    cost_per_query = total_cost / total if total > 0 else 0.0

    ans_count = total - unanswerable_count
    false_abstention_rate = retrieval_failures / ans_count if ans_count > 0 else 0.0
    unans_acc = unanswerable_correct / unanswerable_count if unanswerable_count > 0 else 1.0
    false_ans_rate = (unanswerable_count - unanswerable_correct) / unanswerable_count if unanswerable_count > 0 else 0.0

    decision_reasons: dict[str, int] = {}
    for resp in responses:
        reason = getattr(resp, "decision_reason", "UNKNOWN")
        decision_reasons[reason] = decision_reasons.get(reason, 0) + 1

    return {
        "pilot_cases_evaluated": total,
        "answerable_cases_count": ans_count,
        "unanswerable_cases_count": unanswerable_count,
        "synthetic_usefulness_score": round(usefulness_avg, 2),
        "structural_validation_or_abstention_rate": round(citation_ok / total, 4),
        "source_version_correctness_rate": None,
        "abstention_quality_rate": round(abstention_correct / total, 4),
        "unanswerable_abstention_accuracy": round(unans_acc, 4),
        "false_answer_rate": round(false_ans_rate, 4),
        "false_abstention_rate": round(false_abstention_rate, 4),
        "decision_reasons_breakdown": decision_reasons,
        "user_corrections_count": len(corrections_submitted),
        "user_corrections": corrections_submitted,
        "retrieval_reranking_failures_count": retrieval_failures,
        "p50_latency_ms": round(p50_lat, 2),
        "p95_latency_ms": round(p95_lat, 2),
        "mean_cost_per_query_usd": round(cost_per_query, 6) if all(o.cost is not None for o in obs) else None,
        "model_provider_failures_count": provider_errors,
        "manual_verification_rate": round(manual_verif_rate, 4),
    }
