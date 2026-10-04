#!/usr/bin/env python3
"""Back up operational tables or restore them in a newly created disposable database."""

import argparse
import json
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from services.operations import (
    backup_tables, restore_table_data, verify_backup_integrity, drill_backup_restore_reindex,
)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dsn", default=os.environ.get("FINTAX_DATABASE_URL"))
    parser.add_argument("--dir", type=Path, required=True, help="New private backup directory")
    parser.add_argument("--drill", action="store_true")
    args = parser.parse_args()
    if not args.dsn:
        parser.error("--dsn or FINTAX_DATABASE_URL is required")
    report = drill_backup_restore_reindex(args.dsn, args.dir) if args.drill else backup_tables(args.dsn, args.dir)
    print(json.dumps(report, indent=2))
    return 0 if verify_backup_integrity(args.dir) else 1


if __name__ == "__main__":
    raise SystemExit(main())
