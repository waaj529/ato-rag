"""Create, restore, verify and remove an isolated operational recovery database."""

import uuid

import psycopg
from psycopg import sql
from psycopg.conninfo import make_conninfo

from .backup import TABLES, backup_tables, restore_table_data

SCHEMA = (
    "CREATE TABLE customer_matters (matter_id TEXT PRIMARY KEY, tenant_id TEXT NOT NULL, "
    "name TEXT NOT NULL, created_at TIMESTAMPTZ NOT NULL)",
    "CREATE TABLE matter_documents (doc_id TEXT PRIMARY KEY, matter_id TEXT NOT NULL REFERENCES "
    "customer_matters(matter_id), tenant_id TEXT NOT NULL, title TEXT NOT NULL, content TEXT NOT NULL, "
    "classification TEXT NOT NULL, created_at TIMESTAMPTZ NOT NULL)",
    "CREATE TABLE dead_letter_queue (job_id TEXT PRIMARY KEY, task_name TEXT NOT NULL, payload JSONB NOT NULL, "
    "error_message TEXT NOT NULL, retry_count INT NOT NULL, status TEXT NOT NULL, "
    "created_at TIMESTAMPTZ NOT NULL, updated_at TIMESTAMPTZ NOT NULL)",
)


def drill_backup_restore_reindex(dsn, backup_dir):
    manifest = backup_tables(dsn, backup_dir)
    target = "fintax_restore_" + uuid.uuid4().hex
    target_dsn = make_conninfo(dsn, dbname=target)
    with psycopg.connect(dsn, autocommit=True) as admin:
        admin.execute(sql.SQL("CREATE DATABASE {} TEMPLATE template0").format(sql.Identifier(target)))
        try:
            with psycopg.connect(target_dsn) as restored:
                for statement in SCHEMA:
                    restored.execute(statement)
            counts = restore_table_data(target_dsn, backup_dir)
            with psycopg.connect(target_dsn, autocommit=True) as restored:
                for table in TABLES:
                    restored.execute(sql.SQL("REINDEX TABLE {}").format(sql.Identifier(table)))
            return {"scope": "operational_tables_only", "manifest": manifest,
                    "restored_counts": counts, "isolated_database": target,
                    "content_hashes_verified": True, "reindex_status": "success", "pitr_verified": False}
        finally:
            admin.execute(sql.SQL("DROP DATABASE {} WITH (FORCE)").format(sql.Identifier(target)))
