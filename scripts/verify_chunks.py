#!/usr/bin/env python3
"""Verify a completed FinTaxGPT parent/child chunk export."""

from __future__ import annotations

import argparse
from collections import Counter
import gzip
import json
from pathlib import Path
import sys


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from services.chunker.validation import SourceResolver, validate_source_locator


DEFAULT_ROOT = PROJECT_ROOT / "data/chunks/ato_ready"


def sizing_failure(record: dict, hard_max: int) -> str | None:
    sizing = record.get("sizing")
    if not isinstance(sizing, dict):
        return "missing_sizing"
    units = sizing.get("text_units")
    if sizing.get("method") != "unicode-lexical-v1" or not isinstance(units, int):
        return "invalid_sizing"
    if units > hard_max:
        return "oversized_chunk"
    return None


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=DEFAULT_ROOT)
    args = parser.parse_args()

    report = json.loads((args.root / "chunking_report.json").read_text())
    hard_max = report["config"]["child_hard_max_tokens"]
    resolver = SourceResolver(Path(report["source_import_manifest"]))
    parent_ids: set[str] = set()
    chunk_ids: set[str] = set()
    counts: Counter[str] = Counter()
    failures: Counter[str] = Counter()

    catalog_lineage: set[tuple[str, str]] = set()
    for path in sorted((args.root / "catalog").glob("*.jsonl.gz")):
        with gzip.open(path, "rt", encoding="utf-8") as handle:
            for line in handle:
                record = json.loads(line)
                lineage = (record.get("document_id"), record.get("version_id"))
                if lineage in catalog_lineage:
                    failures["duplicate_catalog_lineage"] += 1
                catalog_lineage.add(lineage)
                if not record.get("source_url"):
                    failures["catalog_missing_source_url"] += 1
                counts["catalog_documents"] += 1

    for path in sorted((args.root / "parents").glob("*.jsonl.gz")):
        with gzip.open(path, "rt", encoding="utf-8") as handle:
          for line in handle:
            record = json.loads(line)
            parent_id = record.get("parent_id")
            if parent_id in parent_ids:
                failures["duplicate_parent_id"] += 1
            parent_ids.add(parent_id)
            counts["parents"] += 1
    for path in sorted((args.root / "children").glob("*.jsonl.gz")):
        with gzip.open(path, "rt", encoding="utf-8") as handle:
          for line in handle:
            record = json.loads(line)
            chunk_id = record.get("chunk_id")
            if chunk_id in chunk_ids:
                failures["duplicate_chunk_id"] += 1
            chunk_ids.add(chunk_id)
            if record.get("parent_chunk_id") not in parent_ids:
                failures["orphan_chunk"] += 1
            sizing_error = sizing_failure(record, hard_max)
            if sizing_error:
                failures[sizing_error] += 1
            if (record.get("document_id"), record.get("version_id")) not in catalog_lineage:
                failures["missing_citation_lineage"] += 1
            required = ("title", "source_url", "publisher", "corpus",
                        "source_class", "applicable_periods", "historical_guidance", "binding_effect",
                        "authority_rank", "page_status", "canonical_reference",
                        "chunk_type", "source_locator")
            if any(key not in record for key in required):
                failures["missing_chunk_metadata"] += 1
            forbidden = ("embedding_model", "embedding_dimension", "indexed_at",
                         "index_namespace")
            if any(key in record for key in forbidden):
                failures["premature_index_metadata"] += 1
            locator_failure = validate_source_locator(record, resolver)
            if locator_failure:
                failures[locator_failure] += 1
            counts["children"] += 1
            counts[f"child_{record.get('chunk_type', 'unknown')}"] += 1

    expected = report["counts"]
    if counts["parents"] != expected.get("parents"):
        failures["parent_count_mismatch"] += 1
    if counts["children"] != expected.get("children"):
        failures["child_count_mismatch"] += 1
    if counts["catalog_documents"] != expected.get("catalog_documents"):
        failures["catalog_count_mismatch"] += 1
    result = {
        "schema_version": "fintax-chunk-verification-1.0",
        "valid": not failures,
        "counts": dict(sorted(counts.items())),
        "failures": dict(sorted(failures.items())),
        "checks": [
            "unique parent ids",
            "unique deterministic chunk ids",
            "no orphan chunks",
            "child hard token maximum",
            "citation and version lineage present",
            "document and chunk metadata present on every child",
            "index metadata absent before embedding/indexing",
            "exact canonical character spans and valid table row ranges",
            "output counts match chunking report",
        ],
    }
    output = args.root / "verification_report.json"
    output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
