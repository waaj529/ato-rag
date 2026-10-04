#!/usr/bin/env python3
"""Grade independently reviewed answers; never infer factual labels from citation membership."""

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from pydantic import TypeAdapter
from services.evaluation import AnswerReview, ReviewedCase, evaluate_review
from services.verification import PipelineResponse


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True, help="JSONL objects with case, response and review")
    parser.add_argument("--output", type=Path, required=True, help="New report path; existing files are refused")
    args = parser.parse_args()
    results = []
    response_schema = TypeAdapter(PipelineResponse)
    for line in args.input.read_text().splitlines():
        if not line.strip():
            continue
        record = json.loads(line)
        results.append(evaluate_review(ReviewedCase.model_validate(record["case"]),
                                       response_schema.validate_python(record["response"]),
                                       AnswerReview.model_validate(record["review"])))
    if not results or len({r["case_id"] for r in results}) != len(results):
        raise ValueError("Evaluation requires non-empty unique reviewed cases")
    claims = [claim for result in results for claim in result["claims"]]
    rate = lambda key: sum(c[key] for c in claims)/len(claims) if claims else None
    answerable = [r for r in results if not r["must_abstain"]]
    unanswerable = [r for r in results if r["must_abstain"]]
    report = {
        "schema_version": "fintax-independent-evaluation-1", "created_at": datetime.now(timezone.utc).isoformat(),
        "evaluation_kind": "independent_human_review",
        "false_answer_rate": sum(not r["abstained"] for r in unanswerable)/len(unanswerable) if unanswerable else None,
        "false_abstention_rate": sum(r["abstained"] for r in answerable)/len(answerable) if answerable else None,
        "cases_evaluated": len(results), "claims_evaluated": len(claims),
        "claim_entailment_rate": rate("entailed"), "authority_correctness": rate("authority_correct"),
        "version_as_of_correctness": rate("version_correct"), "locator_correctness": rate("locator_correct"),
        "unsupported_claim_rate": 1-rate("supported") if claims else None,
        "abstention_correctness": sum(r["abstention_correct"] for r in results)/len(results),
        "broad_production_authorized": False, "cases": results,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("x") as handle:
        json.dump(report, handle, indent=2)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
