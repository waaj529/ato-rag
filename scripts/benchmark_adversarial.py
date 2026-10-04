"""Adversarial unanswerable evaluation suite for FinTaxGPT Phase 7."""

import json
import time
from pathlib import Path

from services.context_builder import ContextPackage, EvidenceUnit
from services.verification import AdequacyStatus, EvidenceAdequacyController, GroundedAnswerPipeline


def run_adversarial_suite() -> dict:
    cases_file = Path("evals/phase7/adversarial_cases.jsonl")
    if not cases_file.exists():
        raise FileNotFoundError(f"Missing {cases_file}")

    controller = EvidenceAdequacyController()
    pipeline = GroundedAnswerPipeline()

    dummy_ev = EvidenceUnit(
        evidence_id="E_ATO_DUMMY", parent_id="p_ATO_DUMMY",
        document_id="doc_dummy", version_id="v1",
        authority_class="legislation", citation_label="ITAA 1997 s 8-1",
        title="Income Tax Assessment Act 1997 s 8-1",
        source_url="https://ato.gov.au/8-1", heading_path=("Part 1",),
        parent_locator={"section_id": "8-1"}, triggering_child_locator={"section_id": "8-1"},
        retrieval_reason="dense", reranker_score=0.45,
        text="General deductions under section 8-1 allow losses or outgoings incurred in gaining assessable income.",
        text_units=30,
    )
    dummy_pkg = ContextPackage(query="irrelevant", evidence=(dummy_ev,), total_text_units=30, settings_version="v1")

    total = 0
    abstained_adequacy = 0
    abstained_pipeline = 0
    false_answers = 0
    results = []

    with open(cases_file, "r", encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            case = json.loads(line)
            total += 1
            cid = case["id"]
            question = case["question"]

            status, reasons = controller.evaluate(question, dummy_pkg)
            if status == AdequacyStatus.INADEQUATE:
                abstained_adequacy += 1

            resp = pipeline.run(question, dummy_pkg)
            if resp.abstained or len(resp.answer.claims) == 0:
                abstained_pipeline += 1
            else:
                false_answers += 1

            results.append({
                "id": cid,
                "status": status.value,
                "abstained": resp.abstained,
                "reasons": reasons,
            })

    metrics = {
        "adversarial_cases_evaluated": total,
        "adequacy_inadequate_rate": round(abstained_adequacy / total, 4),
        "pipeline_abstention_accuracy": round(abstained_pipeline / total, 4),
        "false_answer_rate": round(false_answers / total, 4),
    }

    out_path = Path(f"data/evaluations/phase7_adversarial_{time.time_ns()}.json")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "x", encoding="utf-8") as f:
        json.dump({"metrics": metrics, "details": results}, f, indent=2)

    return metrics


if __name__ == "__main__":
    res = run_adversarial_suite()
    print(json.dumps(res, indent=2))
