#!/usr/bin/env python3
"""Calibrate Kanon 2 cost and vector norms on 128 deterministic corpus inputs."""

import argparse
from datetime import datetime, timezone
import json
import math
import os
from pathlib import Path
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from services.embedding import IsaacusEmbeddingClient, iter_chunk_inputs


DEFAULT_MANIFEST = ROOT / "data/embeddings/kanon2-768-v1/input_manifest.json"
DEFAULT_OUTPUT = ROOT / "data/embeddings/kanon2-768-v1/profile_probe.json"
CHUNK_ROOTS = (ROOT / "data/chunks/ato_ready", ROOT / "data/chunks/court_ready")


def dotenv_value(path: Path, wanted: str) -> str:
    for line in path.read_text().splitlines():
        value = line.strip()
        if not value or value.startswith("#") or "=" not in value:
            continue
        key, raw = value.removeprefix("export ").split("=", 1)
        if key.strip() != wanted:
            continue
        raw = raw.strip()
        if len(raw) >= 2 and raw[0] == raw[-1] and raw[0] in {'"', "'"}:
            raw = raw[1:-1]
        return raw
    raise ValueError(f"{wanted} is missing from {path}")


def evenly_spaced_sample(total: int, size: int = 128):
    targets = {round(index * (total - 1) / (size - 1)) for index in range(size)}
    return [item for index, item in enumerate(iter_chunk_inputs(CHUNK_ROOTS)) if index in targets]


def write_atomic(path: Path, value: dict) -> None:
    descriptor, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            json.dump(value, handle, indent=2, sort_keys=True)
            handle.write("\n")
        os.replace(temporary, path)
    except Exception:
        Path(temporary).unlink(missing_ok=True)
        raise


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--env", type=Path, default=ROOT / ".env")
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    manifest = json.loads(args.manifest.read_text())
    sample = evenly_spaced_sample(manifest["input_count"])
    batch = IsaacusEmbeddingClient(dotenv_value(args.env, "ISAACUS_API_KEY")).embed_documents(
        [item.content for item in sample]
    )
    sample_bytes = sum(len(item.content.encode()) for item in sample)
    estimated_tokens = round(batch.input_tokens * manifest["input_utf8_bytes"] / sample_bytes)
    norms = [math.sqrt(sum(value * value for value in vector)) for vector in batch.vectors]
    report = {
        "schema_version": "fintax-embedding-profile-probe-1.0",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "profile_id": manifest["profile"]["profile_id"],
        "sample_count": len(sample),
        "sample_input_tokens": batch.input_tokens,
        "sample_cost_usd": batch.input_tokens * 0.35 / 1_000_000,
        "estimated_corpus_input_tokens": estimated_tokens,
        "estimated_corpus_cost_usd": estimated_tokens * 0.35 / 1_000_000,
        "estimate_method": "evenly_spaced_128_input_utf8_byte_ratio",
        "vector_dimensions": len(batch.vectors[0]),
        "vector_norm_min": min(norms),
        "vector_norm_max": max(norms),
        "vector_norm_mean": sum(norms) / len(norms),
        "provider_calls_made": 1,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    write_atomic(args.output, report)
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
