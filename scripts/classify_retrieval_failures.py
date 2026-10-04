#!/usr/bin/env python3
"""Merge reviewed failure classes into the frozen Phase 3 evidence report."""

import argparse
from collections import Counter
from datetime import datetime, timezone
import json
from pathlib import Path
import tempfile
import os
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from services.evaluation.failure_classes import CLASSIFICATIONS, V4_CORRECTED_CLASSIFICATIONS


EVIDENCE = ROOT / "data/evaluations/phase3_retrieval_failure_evidence.json"
OUTPUT = ROOT / "data/evaluations/phase3_retrieval_failure_analysis.json"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--evidence", type=Path, default=EVIDENCE)
    parser.add_argument("--output", type=Path, default=OUTPUT)
    parser.add_argument("--cohort", choices=("v2", "v4-corrected"), default="v2")
    args = parser.parse_args()
    classifications = (CLASSIFICATIONS if args.cohort == "v2"
                       else V4_CORRECTED_CLASSIFICATIONS)
    evidence = json.loads(args.evidence.read_text())
    case_ids = {case["case_id"] for case in evidence["cases"]}
    if case_ids != set(classifications):
        raise ValueError("reviewed classifications do not match the frozen miss set")
    records = []
    for case in evidence["cases"]:
        failure_class, notes = classifications[case["case_id"]]
        expected = case["expected_chunks"][0]
        records.append({
            "case_id": case["case_id"], "question": case["question"],
            "expected_document": case["expected_document"],
            "expected_chunk_id": expected["chunk_id"],
            "exact_rank": case["diagnostic_ranks"]["exact"],
            "lexical_rank": case["diagnostic_ranks"]["lexical"],
            "dense_rank": case["diagnostic_ranks"]["dense"],
            "rrf_rank": case["production_ranks"]["fused"],
            "expected_document_chunks": case["expected_document_chunks"],
            "document_ranks": case["document_ranks"],
            "unresolved_identifiers": case["unresolved_identifiers"],
            "metadata": {"active": expected["active"],
                         "embedding_present": expected["embedding_present"]},
            "failure_class": failure_class, "notes": notes,
        })
    aggregate = Counter(record["failure_class"] for record in records)
    report = {
        "schema_version": "fintax-phase3-retrieval-failure-analysis-1.0",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "baseline_settings_version": evidence["baseline_settings_version"],
        "gold_sha256": evidence["gold_sha256"], "case_count": len(records),
        "aggregate": dict(sorted(aggregate.items())), "cases": records,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(prefix=f".{args.output.name}.", dir=args.output.parent)
    with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
        json.dump(report, handle, indent=2, sort_keys=True)
        handle.write("\n")
    os.replace(temporary, args.output)
    print(json.dumps({"output": str(args.output), "aggregate": report["aggregate"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
