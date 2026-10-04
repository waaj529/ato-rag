"""Consistent operational-table backups and guarded restores into fresh drill databases."""

import hashlib
import json
from pathlib import Path
import re

import psycopg
from psycopg import sql
from psycopg.types.json import Jsonb

TABLES = ("customer_matters", "matter_documents", "dead_letter_queue")


def _digest(rows):
    return hashlib.sha256(json.dumps(rows, default=str, sort_keys=True).encode()).hexdigest()


def backup_tables(dsn: str, backup_dir: Path) -> dict:
    backup_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
    manifest = {"scope": "operational_tables_only", "tables": {}}
    with psycopg.connect(dsn) as conn:
        conn.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY")
        manifest["source_database"] = conn.info.dbname
        for table in TABLES:
            cursor = conn.execute(sql.SQL("SELECT * FROM {} ORDER BY 1").format(sql.Identifier(table)))
            rows = cursor.fetchall()
            target = backup_dir / f"{table}.json"
            with target.open("x") as handle:
                target.chmod(0o600)
                json.dump(rows, handle, default=str, sort_keys=True)
            manifest["tables"][table] = {"row_count": len(rows), "sha256": _digest(rows),
                                        "file": target.name, "columns": [c.name for c in cursor.description]}
    with (backup_dir / "backup_manifest.json").open("x") as handle:
        json.dump(manifest, handle, indent=2)
    return manifest


def verify_backup_integrity(backup_dir: Path) -> bool:
    try:
        manifest = json.loads((backup_dir / "backup_manifest.json").read_text())
        if set(manifest["tables"]) != set(TABLES):
            return False
        for table, meta in manifest["tables"].items():
            if meta["file"] != f"{table}.json":
                return False
            rows = json.loads((backup_dir / meta["file"]).read_text())
            if len(rows) != meta["row_count"] or _digest(rows) != meta["sha256"]:
                return False
        return True
    except (OSError, ValueError, KeyError, TypeError):
        return False


def restore_table_data(dsn: str, backup_dir: Path) -> dict:
    if not verify_backup_integrity(backup_dir):
        raise ValueError("Backup integrity check failed")
    manifest = json.loads((backup_dir / "backup_manifest.json").read_text())
    restored = {}
    with psycopg.connect(dsn) as conn:
        if not re.fullmatch(r"fintax_restore_[a-f0-9]{32}", conn.info.dbname):
            raise ValueError("Restore requires a disposable fintax_restore_<uuid> database")
        if conn.info.dbname == manifest["source_database"]:
            raise ValueError("Cannot restore into the source database")
        for table in TABLES:
            if conn.execute(sql.SQL("SELECT count(*) FROM {}").format(sql.Identifier(table))).fetchone()[0]:
                raise ValueError("Restore target tables must be empty")
            meta = manifest["tables"][table]
            rows = json.loads((backup_dir / meta["file"]).read_text())
            statement = sql.SQL("INSERT INTO {} ({}) VALUES ({})").format(
                sql.Identifier(table), sql.SQL(",").join(map(sql.Identifier, meta["columns"])),
                sql.SQL(",").join(sql.Placeholder() for _ in meta["columns"]),
            )
            for row in rows:
                if "payload" in meta["columns"]:
                    idx = meta["columns"].index("payload")
                    row[idx] = Jsonb(row[idx])
                conn.execute(statement, row)
            actual = conn.execute(sql.SQL("SELECT * FROM {} ORDER BY 1").format(sql.Identifier(table))).fetchall()
            if _digest(actual) != meta["sha256"]:
                raise RuntimeError("Restored contents differ from backup")
            restored[table] = len(actual)
    return restored
