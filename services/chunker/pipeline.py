"""Full-corpus chunk pipeline orchestration."""

from datetime import datetime, timezone
import gzip
import hashlib
import json
from pathlib import Path
import time

from .settings import CHUNKER_VERSION, TOKENIZER_VERSION, ChunkerConfig
from .writer import ChunkShardWriter


def _inventory_entries(manifest: dict) -> list[dict]:
    path = Path(manifest["inventory_path"])
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    if digest != manifest["inventory_sha256"]:
        raise ValueError("import inventory hash does not match its manifest")
    with gzip.open(path, "rt", encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def _load_document(root: Path, entry: dict) -> tuple[dict, str]:
    path = root / entry["relative_path"]
    raw = path.read_bytes()
    if hashlib.sha256(raw).hexdigest() != entry["file_sha256"]:
        raise ValueError(f"source changed after import: {path}")
    document = json.loads(raw)
    lineage = (document.get("document_id"), (document.get("version") or {}).get("version_id"))
    if lineage != (entry["document_id"], entry["version_id"]):
        raise ValueError(f"source lineage changed after import: {path}")
    return document, path.parent.name


def chunk_corpus(import_manifest: Path, output: Path, limit: int | None = None) -> dict:
    manifest = json.loads(import_manifest.read_text())
    documents_root = Path(manifest["documents_root"])
    if not documents_root.is_dir():
        raise ValueError(f"imported documents root is unavailable: {documents_root}")
    entries = _inventory_entries(manifest)
    if limit is not None:
        entries = entries[:limit]
    config = ChunkerConfig()
    writer = ChunkShardWriter(output, config)
    started = time.monotonic()
    try:
        for number, entry in enumerate(entries, start=1):
            document, shard = _load_document(documents_root.parent, entry)
            writer.write_document(document, shard)
            if number % 1000 == 0:
                elapsed = time.monotonic() - started
                children = writer.counts["children"]
                print(f"processed={number}/{len(entries)} children={children} "
                      f"elapsed_seconds={elapsed:.1f}", flush=True)
    finally:
        writer.close()
    report = {
        "schema_version": "fintax-chunk-run-1.0", "status": "complete",
        "completed_at": datetime.now(timezone.utc).isoformat(),
        "source_import_manifest": str(import_manifest.resolve()),
        "source_documents": manifest["actual"]["unique_documents"],
        "processed_documents": writer.counts["documents"],
        "limited_run": limit is not None, "chunker_version": CHUNKER_VERSION,
        "tokenizer": TOKENIZER_VERSION, "config": config.__dict__,
        "counts": dict(sorted(writer.counts.items())), "shards": writer.shard_count,
        "elapsed_seconds": round(time.monotonic() - started, 3),
    }
    writer.publish(report)
    return report
