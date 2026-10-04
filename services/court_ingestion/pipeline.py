"""Atomic court-corpus build from an explicit official-source seed manifest."""

from datetime import datetime, timezone
import json
import os
from pathlib import Path
import shutil
import tempfile

from .fetcher import CourtSource, fetch_source, load_local_source
from .parser import parse_judgment
from .records import ready_document


def _verify(record: dict) -> list[str]:
    failures = []
    if record.get("schema_version") != "ready-document-1.0":
        failures.append("wrong schema_version")
    if (record.get("classification") or {}).get("source_class") != "court_decision":
        failures.append("wrong source_class")
    metadata = record.get("case_metadata") or {}
    if metadata.get("neutral_citation") != record.get("canonical_reference_id"):
        failures.append("neutral citation mismatch")
    sections = record.get("sections") or []
    if not sections or any(not item.get("source_locator", {}).get("paragraph_start") for item in sections):
        failures.append("missing paragraph pinpoints")
    return failures


def _source_and_file(item: dict, seed_path: Path, timeout: int):
    values = dict(item)
    local_file = values.pop("local_file", None)
    expected_sha256 = values.pop("expected_sha256", None)
    official_url = values.pop("official_source_url", None)
    if official_url:
        values["source_url"] = official_url
    source = CourtSource(**values)
    if not local_file:
        return source, fetch_source(source, timeout)
    root = seed_path.parent.resolve()
    path = (root / local_file).resolve()
    if not path.is_relative_to(root):
        raise ValueError("manual court file escapes the manifest directory")
    if not expected_sha256:
        raise ValueError("manual court file requires expected_sha256")
    return source, load_local_source(source, path, expected_sha256)


def build_corpus(seed_path: Path, output: Path, timeout: int = 30,
                 audit_path: Path | None = None) -> dict:
    """Fetch and publish a new corpus; refuse to replace an existing output."""
    if output.exists():
        raise ValueError(f"refusing to replace existing corpus: {output}")
    seeds = json.loads(seed_path.read_text())
    staging = Path(tempfile.mkdtemp(prefix=f".{output.name}-", dir=output.parent))
    rows, failures = [], []
    try:
        for item in seeds:
            try:
                source, fetched = _source_and_file(item, seed_path, timeout)
                parsed = parse_judgment(fetched.body, source.neutral_citation,
                                        fetched.content_type)
            except (OSError, ValueError) as error:
                citation = item.get("neutral_citation", "unknown citation")
                failures.append(f"{citation}: {error}")
                continue
            record = ready_document(fetched, parsed)
            record_failures = _verify(record)
            if record_failures:
                failures.extend(f"{source.neutral_citation}: {value}" for value in record_failures)
                continue
            relative = f"documents/{record['document_id'][:2]}/{record['document_id']}.json"
            path = staging / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(record, ensure_ascii=False, separators=(",", ":")) + "\n")
            raw_path = staging / record["provenance"]["raw_object_key"]
            raw_path.parent.mkdir(parents=True, exist_ok=True)
            raw_path.write_bytes(fetched.body)
            rows.append({"document_id": record["document_id"], "path": relative,
                         "neutral_citation": source.neutral_citation})
        report = {"valid_for_chunking": bool(rows), "attempted": len(seeds),
                  "document_count": len(rows), "skipped": len(failures), "failures": failures}
        if audit_path:
            audit_path.parent.mkdir(parents=True, exist_ok=True)
            audit_path.write_text(json.dumps(report, indent=2) + "\n")
        if not rows:
            raise ValueError("no court seed was ingested: " + "; ".join(failures))
        index = staging / "indexes/court_decision/all.jsonl"
        index.parent.mkdir(parents=True, exist_ok=True)
        index.write_text("".join(json.dumps(row, separators=(",", ":")) + "\n" for row in rows))
        (staging / "verification_report.json").write_text(json.dumps(report, indent=2) + "\n")
        summary = {"total_ready_documents": len(rows),
                   "completed_at": datetime.now(timezone.utc).isoformat()}
        (staging / "export_summary.json").write_text(json.dumps(summary, indent=2) + "\n")
        os.replace(staging, output)
        return report
    except Exception:
        shutil.rmtree(staging, ignore_errors=True)
        raise
