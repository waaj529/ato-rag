#!/usr/bin/env python3
"""Publish deterministic exact identifiers for the active Phase 3 chunks."""

import argparse
import json
import os
from pathlib import Path
import sys

import psycopg

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from services.retrieval import populate_exact_identifiers


DEFAULT_DSN = "postgresql://fintaxgpt:fintaxgpt-local-only@127.0.0.1:5433/fintaxgpt"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dsn", default=os.environ.get("FINTAX_DATABASE_URL", DEFAULT_DSN))
    args = parser.parse_args()
    with psycopg.connect(args.dsn) as connection:
        counts = populate_exact_identifiers(connection)
        total = connection.execute("SELECT count(*) FROM exact_identifiers").fetchone()[0]
    print(json.dumps({"inserted": counts, "total": total}, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
