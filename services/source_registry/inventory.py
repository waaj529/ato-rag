"""Build a frozen, content-hashed inventory from corpus partition indexes."""

from collections import Counter
import gzip
import hashlib
import json
from pathlib import Path

from .conflicts import conflict_report


def _indexed_paths(source: Path) -> tuple[list[str], dict]:
    rows, primary_rows, paths = 0, 0, set()
    for index in sorted((source / "indexes").glob("*/*.jsonl")):
        with index.open() as handle:
            for line in handle:
                if not line.strip():
                    continue
                row = json.loads(line)
                relative = row.get("path") or row.get("relative_path")
                if not relative:
                    raise ValueError(f"index row has no path: {index}")
                paths.add(relative)
                rows += 1
                primary_rows += "primary_legislation" in index.parts
    return sorted(paths), {"rows": rows, "unique_paths": len(paths),
                           "duplicate_rows": rows - len(paths),
                           "primary_legislation_rows": primary_rows}


def build_inventory(source: Path, required_schema: str) -> tuple[list[dict], dict]:
    paths, index_audit = _indexed_paths(source)
    entries, ids, corpora = [], set(), Counter()
    errors = Counter()
    document_bytes = 0
    identities = []
    for relative in paths:
        path = source / relative
        if not path.is_file():
            errors["missing_file"] += 1
            continue
        raw = path.read_bytes()
        document_bytes += len(raw)
        try:
            record = json.loads(raw)
        except json.JSONDecodeError:
            errors["invalid_json"] += 1
            continue
        document_id = record.get("document_id")
        if document_id in ids:
            errors["duplicate_document_id"] += 1
        ids.add(document_id)
        if record.get("schema_version") != required_schema:
            errors["schema_mismatch"] += 1
        version = record.get("version") or {}
        entries.append({"relative_path": relative, "document_id": document_id,
                        "version_id": version.get("version_id"),
                        "file_sha256": hashlib.sha256(raw).hexdigest()})
        identities.append((record.get("source_url"), version.get("version_id"),
                           version.get("content_sha256")))
        corpus = (record.get("classification") or {}).get("corpus", "unknown")
        corpora[corpus] += 1
    if errors:
        raise ValueError(f"indexed corpus validation failed: {dict(errors)}")
    disk_files = sum(1 for _ in (source / "documents").glob("*/*.json"))
    audit = {**index_audit, **conflict_report(identities), "document_bytes": document_bytes,
             "by_corpus": dict(sorted(corpora.items())),
             "unindexed_document_files": disk_files - len(entries)}
    return entries, audit


def write_inventory(path: Path, entries: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with gzip.open(path, "wt", encoding="utf-8") as handle:
        for entry in entries:
            handle.write(json.dumps(entry, separators=(",", ":")) + "\n")

