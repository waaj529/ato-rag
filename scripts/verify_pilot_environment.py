#!/usr/bin/env python3
"""Verify deployed environment readiness before accepting private customer data (Phase 7)."""

import argparse
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import sys
import time

import psycopg

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from packages.security import CircuitBreaker, CircuitBreakerOpenError, get_secret, redact_text, sanitize_trace_metadata, scoped_tenant_connection
from scripts.backup_restore_ops import drill_backup_restore_reindex

DEFAULT_DSN = "postgresql://fintaxgpt:fintaxgpt-local-only@127.0.0.1:5433/fintaxgpt"
BACKUP_DIR = ROOT / "data/backups/pilot_env_drill"


def check_pitr_and_storage(conn: psycopg.Connection) -> list[str]:
    fails = []
    wal = conn.execute("SELECT setting FROM pg_settings WHERE name = 'wal_level'").fetchone()[0]
    if wal not in {"replica", "logical"}:
        fails.append(f"PostgreSQL PITR: wal_level is '{wal}', expected 'replica'")
    manifest = ROOT / "data/imports/ato_ready.json"
    chunk_meta = ROOT / "data/chunks/ato_ready/chunking_report.json"
    if not manifest.exists() or "inventory_sha256" not in manifest.read_text():
        fails.append("Object-store versioning: manifest lacks immutable inventory_sha256")
    if not chunk_meta.exists() or "chunker_version" not in chunk_meta.read_text():
        fails.append("Object-store versioning: chunk storage lacks immutable chunker_version")
    fails.append("WAL archival and point-in-time recovery are not verified by wal_level")
    fails.append("Object-storage versioning has not been checked against a deployed storage API")
    return fails


def check_restore_and_pool_rls(dsn: str, backup_dir: Path) -> list[str]:
    fails = []
    try:
        drill_backup_restore_reindex(dsn, backup_dir)
    except Exception as exc:
        fails.append(f"Backup/restore/reindex drill failed: {exc}")

    with psycopg.connect(dsn, autocommit=True) as conn:
        with scoped_tenant_connection(conn, "pilot-tenant-A"):
            conn.execute("INSERT INTO customer_matters (matter_id, tenant_id, name) VALUES ('m-pA', 'pilot-tenant-A', 'M A') ON CONFLICT DO NOTHING")
            conn.execute("INSERT INTO matter_documents (doc_id, matter_id, tenant_id, title, content) VALUES ('d-pA', 'm-pA', 'pilot-tenant-A', 'D A', 'Secret A') ON CONFLICT DO NOTHING")
        try:
            with scoped_tenant_connection(conn, "pilot-tenant-A"):
                raise RuntimeError("simulated aborted tx")
        except RuntimeError:
            pass
        if conn.execute("SELECT doc_id FROM matter_documents").fetchall():
            fails.append("Pooled connection RLS isolation failed: unscoped query observed rows")
    return fails


def check_security_and_redaction() -> list[str]:
    fails = []
    if not get_secret("FINTAX_DATABASE_URL", default="secret-token-12345"):
        fails.append("Secrets provider: failed to resolve secrets")
    pii = "Taxpayer TFN 987 654 321, ABN 12 345 678 901"
    if "987 654 321" in redact_text(pii, "CUSTOMER_CONFIDENTIAL"):
        fails.append("Privacy redaction: synthetic TFN leaked into text output")
    meta = sanitize_trace_metadata({"user_prompt": pii, "cost": 0.01}, "CUSTOMER_CONFIDENTIAL")
    if "987 654 321" in meta["user_prompt"] or meta["cost"] != 0.01:
        fails.append("Privacy redaction: synthetic TFN leaked into trace metadata")
    cb = CircuitBreaker(failure_threshold=1, recovery_timeout=60.0)
    try:
        cb.call(lambda: (_ for _ in ()).throw(ConnectionError("down")))
    except ConnectionError:
        pass
    try:
        cb.call(lambda: "ok")
        fails.append("Circuit breaker: did not fail-fast on outage")
    except CircuitBreakerOpenError:
        pass
    return fails


def check_freshness_and_load(dsn: str) -> list[str]:
    fails = []
    with psycopg.connect(dsn) as conn:
        if conn.execute("SELECT count(*) FROM retrieval_chunks WHERE is_active = true").fetchone()[0] < 1000:
            fails.append("Source freshness: active chunks below threshold")
        start = time.perf_counter()
        canary = conn.execute("SELECT chunk_id FROM retrieval_chunks WHERE canonical_reference_id = 'ITAA 1997 s 108-5' LIMIT 1").fetchone()
        latency = (time.perf_counter() - start) * 1000
        if not canary or latency > 250:
            fails.append(f"Canary query failed or too slow ({latency:.2f}ms)")

    def query_task(_):
        with psycopg.connect(dsn) as c:
            return c.execute("SELECT chunk_id FROM retrieval_chunks ORDER BY chunk_id LIMIT 5").fetchall()

    with ThreadPoolExecutor(max_workers=10) as executor:
        results = list(executor.map(query_task, range(20)))
    if len(results) != 20:
        fails.append("Peak load test failed")
    return fails


def verify_pilot_environment(dsn: str = DEFAULT_DSN, backup_dir: Path = BACKUP_DIR) -> dict:
    fails = []
    with psycopg.connect(dsn) as conn:
        fails.extend(check_pitr_and_storage(conn))
    fails.extend(check_restore_and_pool_rls(dsn, backup_dir))
    fails.extend(check_security_and_redaction())
    fails.extend(check_freshness_and_load(dsn))
    return {
        "schema_version": "fintax-pilot-environment-verification-1.0",
        "verified_at": datetime.now(timezone.utc).isoformat(),
        "ready_for_pilot": not fails,
        "failures": fails,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dsn", default=os.environ.get("FINTAX_DATABASE_URL", DEFAULT_DSN))
    args = parser.parse_args()
    report = verify_pilot_environment(dsn=args.dsn)
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["ready_for_pilot"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
