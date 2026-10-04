"""Phase 7 safety and usability acceptance classification."""

FALSE_ABSTENTION_TARGET = 0.05


def classify_acceptance(metrics: dict) -> tuple[str, dict]:
    safety_passed = (
        metrics.get("evaluation_kind") == "independent_human_review"
        and metrics.get("cases_evaluated", 0) > 0
        and metrics.get("claims_evaluated", 0) > 0
        and metrics.get("unsupported_claim_rate") == 0.0
        and metrics.get("authority_correctness") == 1.0
        and metrics.get("false_answer_rate") == 0.0
        and metrics.get("locator_correctness") == 1.0
        and metrics.get("version_as_of_correctness") == 1.0
    )
    false_abstention_rate = metrics.get("false_abstention_rate", 1.0)
    usability_passed = isinstance(false_abstention_rate, (float, int)) and 0 <= false_abstention_rate <= FALSE_ABSTENTION_TARGET
    status = "safe_for_staging" if safety_passed else "acceptance_failed"
    return status, {
        "safety_gate": "passed" if safety_passed else "failed",
        "false_answer_rate": metrics.get("false_answer_rate"),
        "citation_correctness_rate": metrics.get("locator_correctness"),
        "source_version_correctness_rate": metrics.get("version_as_of_correctness"),
        "usability_gate": "passed" if usability_passed else "target_not_yet_met",
        "false_abstention_rate": false_abstention_rate,
        "target_false_abstention_rate": FALSE_ABSTENTION_TARGET,
        "staging_authorized": safety_passed,
        # Staging evidence cannot authorize broad production by itself.
        "broad_production_authorized": False,
    }
