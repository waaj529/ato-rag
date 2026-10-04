#!/usr/bin/env python3
"""Atomically publish frozen parent chunks for Phase 4 context expansion."""

import argparse
import gzip
import json
import os
from pathlib import Path
import sys

import psycopg
from psycopg.types.json import Jsonb

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

DEFAULT_DSN = "postgresql://fintaxgpt:fintaxgpt-local-only@127.0.0.1:5433/fintaxgpt"
MANIFEST = ROOT / "data/embeddings/kanon2-768-v1/input_manifest.json"
COLUMNS = (
    "parent_id", "document_id", "version_id", "source_class",
    "canonical_reference_id", "authority_rank", "title", "source_url",
    "block_type", "heading_path", "source_locator", "content", "text_units",
    "chunker_version", "is_active",
)


def _records(directory: Path):
    for path in sorted(directory.glob("*.jsonl.gz")):
        with gzip.open(path, "rt", encoding="utf-8") as handle:
            for line in handle:
                if line.strip():
                    yield json.loads(line)


def _catalog(root: Path) -> dict[tuple[str, str], dict]:
    return {(row["document_id"], row["version_id"]): row
            for row in _records(root / "catalog")}


def _row(parent: dict, catalog: dict) -> tuple:
    metadata = catalog[(parent["document_id"], parent["version_id"])]
    classification = metadata.get("classification") or {}
    return (
        parent["parent_id"], parent["document_id"], parent["version_id"],
        metadata["source_class"], metadata.get("canonical_reference_id"),
        metadata.get("authority_rank"), metadata["title"], metadata["source_url"],
        parent["block_type"], Jsonb(parent.get("heading_path") or []),
        Jsonb(parent["locator"]), parent["content"], parent["sizing"]["text_units"],
        parent["chunker_version"], True,
    )


def publish(connection: psycopg.Connection, roots: tuple[Path, ...]) -> int:
    connection.execute(
        "CREATE TEMP TABLE phase4_parent_stage "
        "(LIKE retrieval_parents INCLUDING DEFAULTS INCLUDING CONSTRAINTS) ON COMMIT DROP"
    )
    count = 0
    copy_sql = f"COPY phase4_parent_stage ({','.join(COLUMNS)}) FROM STDIN"
    with connection.cursor() as cursor, cursor.copy(copy_sql) as copy:
        for root in roots:
            catalog = _catalog(root)
            for parent in _records(root / "parents"):
                copy.write_row(_row(parent, catalog))
                count += 1
    staged = connection.execute("SELECT count(*) FROM phase4_parent_stage").fetchone()[0]
    if staged != count:
        raise RuntimeError(f"staged {staged} of {count} parent records")
    orphaned = connection.execute(
        """SELECT count(*) FROM retrieval_chunks child
           LEFT JOIN phase4_parent_stage parent
             ON parent.parent_id=child.parent_chunk_id
           WHERE child.is_active AND parent.parent_id IS NULL"""
    ).fetchone()[0]
    if orphaned:
        raise RuntimeError(f"{orphaned} active children have no staged parent")
    connection.execute("TRUNCATE retrieval_parents")
    connection.execute("INSERT INTO retrieval_parents SELECT * FROM phase4_parent_stage")
    connection.commit()
    return count


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dsn", default=os.environ.get("FINTAX_DATABASE_URL", DEFAULT_DSN))
    parser.add_argument("--manifest", type=Path, default=MANIFEST)
    args = parser.parse_args()
    manifest = json.loads(args.manifest.read_text())
    roots = tuple(Path(value) for value in manifest["chunk_roots"])
    with psycopg.connect(args.dsn) as connection:
        count = publish(connection, roots)
    print(json.dumps({"published_parents": count, "roots": [str(root) for root in roots]}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
