"""Validation and registration for ready-document corpora."""

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path

from .inventory import build_inventory, write_inventory


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def import_corpus(source: Path, config: dict, inventory_path: Path) -> dict:
    source = source.expanduser().resolve()
    verification_path = source / "verification_report.json"
    summary_path = source / "export_summary.json"
    if not (source / "documents").is_dir() or not verification_path.is_file():
        raise ValueError(f"incomplete ready corpus: {source}")
    verification = json.loads(verification_path.read_text())
    flag = config["required_verification_flag"]
    if verification.get(flag) is not True:
        raise ValueError(f"source verification flag {flag!r} is not true")
    entries, audit = build_inventory(source, config["required_schema"])
    write_inventory(inventory_path, entries)
    summary = json.loads(summary_path.read_text()) if summary_path.exists() else {}
    return {
        "schema_version": "fintax-corpus-import-1.0", "corpus_id": config["corpus_id"],
        "imported_at": datetime.now(timezone.utc).isoformat(), "source_root": str(source),
        "documents_root": str(source / "documents"), "source_schema": config["required_schema"],
        "inventory_path": str(inventory_path.resolve()),
        "inventory_sha256": file_sha256(inventory_path),
        "source_verification": {"valid_for_chunking": True,
            "report_path": str(verification_path),
            "report_sha256": file_sha256(verification_path)},
        "actual": {"unique_documents": len(entries),
            "document_bytes": audit["document_bytes"],
            "by_corpus": audit["by_corpus"], "invalid_json": 0,
            "duplicate_document_ids": 0,
            "unindexed_document_files": audit["unindexed_document_files"]},
        "source_reported": {"total_ready_documents": summary.get("total_ready_documents"),
            "primary_legislation_sections": summary.get("primary_legislation_sections")},
        "index_audit": {key: value for key, value in audit.items()
                        if key not in {"document_bytes", "by_corpus",
                                       "unindexed_document_files"}},
        "import_policy": "content_hashed_index_inventory_no_corpus_copy",
    }

