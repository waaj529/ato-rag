#!/usr/bin/env python3
"""Freeze deterministic Phase 3 embedding inputs without calling the provider."""

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from services.embedding import KANON2_768_V1, iter_chunk_inputs


DEFAULT_ROOTS = (ROOT / "data/chunks/ato_ready", ROOT / "data/chunks/court_ready")
DEFAULT_OUTPUT = ROOT / "data/embeddings/kanon2-768-v1/input_manifest.json"


def build_manifest(chunk_roots: tuple[Path, ...]) -> dict:
    digest = hashlib.sha256()
    count = 0
    input_bytes = 0
    for item in iter_chunk_inputs(chunk_roots):
        digest.update(item.chunk_id.encode())
        digest.update(item.input_sha256.encode())
        count += 1
        input_bytes += len(item.content.encode())
    profile = KANON2_768_V1
    return {
        "schema_version": "fintax-embedding-input-manifest-1.0",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "profile": {
            "profile_id": profile.profile_id,
            "provider": profile.provider,
            "model": profile.model,
            "dimensions": profile.dimensions,
            "document_task": profile.document_task,
            "query_task": profile.query_task,
            "overflow_strategy": profile.overflow_strategy,
            "normalization": profile.normalization,
            "status": profile.status,
        },
        "chunk_roots": [str(path.resolve()) for path in chunk_roots],
        "input_count": count,
        "request_batches_at_128": (count + 127) // 128,
        "input_utf8_bytes": input_bytes,
        "corpus_revision_sha256": digest.hexdigest(),
        "provider_calls_made": 0,
    }


def write_atomic(path: Path, manifest: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            json.dump(manifest, handle, indent=2, sort_keys=True)
            handle.write("\n")
        os.replace(temporary, path)
    except Exception:
        Path(temporary).unlink(missing_ok=True)
        raise


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--chunk-root", action="append", type=Path)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    roots = tuple(args.chunk_root) if args.chunk_root else DEFAULT_ROOTS
    manifest = build_manifest(roots)
    write_atomic(args.output, manifest)
    print(json.dumps(manifest, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
