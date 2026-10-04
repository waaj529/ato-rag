"""Evaluation runner executing DeepEval test suites and compiling reports."""

from datetime import datetime, timezone
from typing import Any, Sequence

from deepeval.test_case import LLMTestCase


def evaluate_test_case(test_case: LLMTestCase, metrics: Sequence[Any]) -> dict[str, Any]:
    metric_results = {}
    passed = True
    for metric in metrics:
        metric.measure(test_case)
        metric_name = getattr(metric, "__name__", metric.__class__.__name__)
        score = getattr(metric, "score", 0.0)
        reason = getattr(metric, "reason", None)
        success = metric.is_successful() if hasattr(metric, "is_successful") else bool(score >= getattr(metric, "threshold", 0.5))
        metric_results[metric_name] = {
            "score": score,
            "success": success,
            "reason": reason,
        }
        if not success:
            passed = False

    return {
        "input": test_case.input,
        "actual_output": test_case.actual_output,
        "retrieval_context_count": len(test_case.retrieval_context or []),
        "passed": passed,
        "metrics": metric_results,
    }


def run_deepeval_suite(
    test_cases: Sequence[LLMTestCase],
    metrics: Sequence[Any],
) -> dict[str, Any]:
    if not test_cases:
        raise ValueError("Cannot evaluate an empty test case list")
    if not metrics:
        raise ValueError("Evaluation requires at least one metric")

    case_results = [evaluate_test_case(tc, metrics) for tc in test_cases]
    metric_names = list(case_results[0]["metrics"].keys())

    aggregates = {}
    for name in metric_names:
        scores = [cr["metrics"][name]["score"] for cr in case_results if name in cr["metrics"] and cr["metrics"][name]["score"] is not None]
        mean_score = sum(scores) / len(scores) if scores else 0.0
        success_count = sum(1 for cr in case_results if cr["metrics"][name]["success"])
        aggregates[name] = {
            "mean_score": round(mean_score, 4),
            "pass_rate": round(success_count / len(case_results), 4),
        }

    total_passed = sum(1 for cr in case_results if cr["passed"])
    return {
        "schema_version": "fintax-deepeval-evaluation-1",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "total_cases": len(case_results),
        "all_passed": total_passed == len(case_results),
        "overall_pass_rate": round(total_passed / len(case_results), 4),
        "metric_aggregates": aggregates,
        "cases": case_results,
    }
