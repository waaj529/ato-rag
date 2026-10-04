"""Run resumable Kanon 2 document embedding into PostgreSQL/pgvector."""

import argparse
import json
import os
from pathlib import Path
import sys

import psycopg

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.probe_embedding_profile import dotenv_value
from services.embedding import IsaacusEmbeddingClient, iter_chunk_inputs, run_embeddings
from services.indexing import RetrievalStore


CHUNK_ROOTS = (ROOT / "data/chunks/ato_ready", ROOT / "data/chunks/court_ready")
MANIFEST = ROOT / "data/embeddings/kanon2-768-v1/input_manifest.json"
DEFAULT_DSN = "postgresql://fintaxgpt:fintaxgpt-local-only@127.0.0.1:5433/fintaxgpt"
DEFAULT_TOKEN_CEILING = 171_000_000


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--env", type=Path, default=ROOT / ".env")
    parser.add_argument("--dsn", default=os.environ.get("FINTAX_DATABASE_URL", DEFAULT_DSN))
    parser.add_argument("--batch-size", type=int, default=128)
    parser.add_argument("--max-batches", type=int)
    parser.add_argument("--max-corpus-tokens", type=int, default=DEFAULT_TOKEN_CEILING)
    args = parser.parse_args()
    manifest = json.loads(MANIFEST.read_text())
    client = IsaacusEmbeddingClient(dotenv_value(args.env, "ISAACUS_API_KEY"))

    def progress(batches: int, embedded: int, tokens: int) -> None:
        if batches == 1 or batches % 10 == 0:
            print(json.dumps({"batches": batches, "embedded": embedded,
                              "input_tokens": tokens}), flush=True)

    with psycopg.connect(args.dsn) as connection:
        result = run_embeddings(
            iter_chunk_inputs(CHUNK_ROOTS), client, RetrievalStore(connection),
            manifest["corpus_revision_sha256"], args.batch_size,
            args.max_batches, progress, args.max_corpus_tokens,
        )
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
