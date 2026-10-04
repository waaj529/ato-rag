#!/usr/bin/env python3
"""Run DeepEval RAG evaluations on generation outputs and retrieved evidence."""

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from services.evaluation import (
    build_rag_metric_suite,
    create_llm_test_case,
    run_deepeval_suite,
)


def parse_record(line: str):
    data = json.loads(line)
    query = data.get("query") or data.get("input") or data.get("question")
    actual_output = data.get("actual_output") or data.get("answer") or data.get("answer_markdown")
    retrieval_context = data.get("retrieval_context") or data.get("context") or []
    expected_output = data.get("expected_output") or data.get("expected_answer")
    return create_llm_test_case(
        query=query,
        actual_output=actual_output,
        retrieval_context=retrieval_context,
        expected_output=expected_output,
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True, help="Input JSONL file containing evaluation cases")
    parser.add_argument("--output", type=Path, required=True, help="Output JSON report path; existing files refused")
    parser.add_argument("--threshold", type=float, default=0.7, help="Metric success threshold (default: 0.7)")
    parser.add_argument("--model", type=str, default=None, help="LLM judge model identifier (default: DeepEval default)")
    parser.add_argument("--limit", type=int, default=None, help="Maximum number of cases to evaluate")
    parser.add_argument("--force", action="store_true", help="Force overwrite existing output file")
    args = parser.parse_args()

    if args.output.exists() and not args.force:
        raise FileExistsError(f"Refusing overwrite of existing report at {args.output}")

    lines = [line.strip() for line in args.input.read_text().splitlines() if line.strip()]
    if args.limit:
        lines = lines[:args.limit]
    if not lines:
        raise ValueError(f"No records found in {args.input}")

    test_cases = [parse_record(line) for line in lines]
    metrics = build_rag_metric_suite(threshold=args.threshold, model=args.model)
    report = run_deepeval_suite(test_cases, metrics)
    report["input_file"] = str(args.input)
    report["judge_model"] = args.model or "deepeval_default"

    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w") as handle:
        json.dump(report, handle, indent=2)

    print(f"DeepEval evaluation complete: {report['total_cases']} cases evaluated.")
    print(f"Overall pass rate: {report['overall_pass_rate']:.1%}")
    for name, agg in report["metric_aggregates"].items():
        print(f" - {name}: mean={agg['mean_score']:.2f}, pass_rate={agg['pass_rate']:.1%}")
    return 0 if report["all_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
