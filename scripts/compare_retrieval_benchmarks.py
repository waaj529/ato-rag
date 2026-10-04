#!/usr/bin/env python3
"""Write a compact metric comparison between two retrieval benchmark reports."""

import argparse
import json
from pathlib import Path
import tempfile
import os


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("baseline", type=Path)
    parser.add_argument("candidate", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    baseline = json.loads(args.baseline.read_text())
    candidate = json.loads(args.candidate.read_text())
    metrics = sorted(baseline["overall"])
    comparison = {
        "schema_version": "fintax-phase3-retrieval-comparison-1.0",
        "baseline_settings_version": baseline["settings_version"],
        "candidate_settings_version": candidate["settings_version"],
        "gold_sha256": candidate["gold_sha256"],
        "baseline_failures": len(baseline["failures"]),
        "candidate_failures": len(candidate["failures"]),
        "failure_delta": len(candidate["failures"]) - len(baseline["failures"]),
        "abstention_accuracy": {"baseline": baseline["abstention_accuracy"],
                                "candidate": candidate["abstention_accuracy"]},
        "recall": {metric: {"baseline": baseline["overall"][metric],
                            "candidate": candidate["overall"][metric],
                            "delta": candidate["overall"][metric]
                            - baseline["overall"][metric]} for metric in metrics},
        "latency_ms": {name: {"baseline": baseline["latency_ms"][name],
                              "candidate": candidate["latency_ms"][name],
                              "delta": candidate["latency_ms"][name]
                              - baseline["latency_ms"][name]}
                       for name in ("p50", "p95")},
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(prefix=f".{args.output.name}.",
                                              dir=args.output.parent)
    with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
        json.dump(comparison, handle, indent=2, sort_keys=True)
        handle.write("\n")
    os.replace(temporary, args.output)
    print(json.dumps(comparison, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
