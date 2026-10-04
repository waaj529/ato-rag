#!/usr/bin/env python3
"""Machine-verifiable Phase 6 Security and Operations exit runner."""

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import sys

import psycopg

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from packages.security import audit_security_controls
from scripts.backup_restore_ops import drill_backup_restore_reindex
from scripts.verify_phase3_exit import verify_phase3_exit
from scripts.verify_phase5_exit import verify_phase5_exit

DEFAULT_DSN = "postgresql://fintaxgpt:fintaxgpt-local-only@127.0.0.1:5433/fintaxgpt"
BACKUP_DIR = ROOT / "data/backups/phase6_exit_test"


def check_backup_and_regressions(dsn: str, backup_dir: Path) -> list[str]:
    fails = []
    drill_backup_restore_reindex(dsn, backup_dir)
    fails.append("Deployed PITR and object-storage versioning have not been independently verified")
    with psycopg.connect(dsn) as conn:
        idxs = conn.execute("SELECT count(*) FROM pg_indexes WHERE tablename = 'retrieval_chunks'").fetchone()[0]
        if idxs < 2:
            fails.append("derived retrieval indexes missing")
    if not verify_phase3_exit().get("passed"):
        fails.append("Phase 3 regression failure")
    p4 = ROOT / "data/evaluations/phase4_end_to_end_verification.json"
    if not p4.exists() or not json.loads(p4.read_text()).get("passed"):
        fails.append("Phase 4 regression failure")
    if not verify_phase5_exit().get("passed"):
        fails.append("Phase 5 regression failure")
    return fails


def verify_phase6_exit(dsn: str = DEFAULT_DSN, backup_dir: Path = BACKUP_DIR) -> dict:
    with psycopg.connect(dsn, autocommit=True) as conn:
        security_failures = audit_security_controls(conn)
    ops_failures = check_backup_and_regressions(dsn, backup_dir)
    failures = [*security_failures, *ops_failures]
    return {
        "schema_version": "fintax-phase6-exit-verification-1.0",
        "verified_at": datetime.now(timezone.utc).isoformat(),
        "status": "blocked" if failures else "technical_checks_passed",
        "passed": not failures,
        "failures": failures,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dsn", default=os.environ.get("FINTAX_DATABASE_URL", DEFAULT_DSN))
    args = parser.parse_args()
    report = verify_phase6_exit(dsn=args.dsn)
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
