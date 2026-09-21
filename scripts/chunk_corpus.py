#!/usr/bin/env python3
"""Generate deterministic parent/child chunks from an imported corpus."""

import argparse
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from services.chunker.pipeline import chunk_corpus


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--import-manifest", type=Path,
                        default=ROOT / "data/imports/ato_ready.json")
    parser.add_argument("--output", type=Path,
                        default=ROOT / "data/chunks/ato_ready")
    parser.add_argument("--limit", type=int)
    args = parser.parse_args()
    try:
        report = chunk_corpus(args.import_manifest, args.output, args.limit)
    except ValueError as error:
        raise SystemExit(str(error)) from error
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

