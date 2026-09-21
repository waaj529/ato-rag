#!/usr/bin/env python3
"""Register a verified ready-document corpus without copying it."""

import argparse
import json
import os
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from services.source_registry.ready_import import import_corpus


DEFAULT_CONFIG = ROOT / "packages/config/corpora/ato_ready.json"
DEFAULT_OUTPUT = ROOT / "data/imports/ato_ready.json"
DEFAULT_INVENTORY = ROOT / "data/imports/ato_ready_inventory.jsonl.gz"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--inventory", type=Path, default=DEFAULT_INVENTORY)
    args = parser.parse_args()
    config = json.loads(args.config.read_text())
    fallback = os.environ.get(config["source_env"], config["default_source"])
    try:
        manifest = import_corpus(args.source or Path(fallback), config, args.inventory)
    except ValueError as error:
        raise SystemExit(str(error)) from error
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    print(json.dumps(manifest, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
