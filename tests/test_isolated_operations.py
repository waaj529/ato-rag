"""Real PostgreSQL restore and pooled transaction checks in disposable databases."""

from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
import uuid

import psycopg
from psycopg import sql
from psycopg.conninfo import make_conninfo
from psycopg_pool import ConnectionPool
import pytest

from packages.security import PermissionScope
from services.answering.database import check_connection, request_connection
from services.operations import drill_backup_restore_reindex, restore_table_data
from services.operations.restore import SCHEMA

DSN = "postgresql://fintaxgpt:fintaxgpt-local-only@127.0.0.1:5433/fintaxgpt"


@pytest.fixture
def isolated_database():
    name = "fintax_test_" + uuid.uuid4().hex
    dsn = make_conninfo(DSN, dbname=name)
    with psycopg.connect(DSN, autocommit=True) as admin:
        admin.execute(sql.SQL("CREATE DATABASE {} TEMPLATE template0").format(sql.Identifier(name)))
        try:
            with psycopg.connect(dsn) as conn:
                for statement in SCHEMA:
                    conn.execute(statement)
                conn.execute("INSERT INTO customer_matters VALUES ('mA','tenant-A','Matter A',NOW()), ('mB','tenant-B','Matter B',NOW())")
                conn.execute("INSERT INTO matter_documents VALUES ('docA','mA','tenant-A','Title','Private text','CUSTOMER_CONFIDENTIAL',NOW())")
                conn.execute("INSERT INTO dead_letter_queue VALUES ('job1','embed','{\"doc_id\":\"docA\"}','timeout',0,'FAILED',NOW(),NOW())")
            yield dsn
        finally:
            admin.execute(sql.SQL("DROP DATABASE {} WITH (FORCE)").format(sql.Identifier(name)))


def test_backup_actually_restores_rows_and_rebuilds_indexes_in_different_database(isolated_database, tmp_path):
    report = drill_backup_restore_reindex(isolated_database, tmp_path / "backup")
    assert report["content_hashes_verified"] is True
    assert report["restored_counts"] == {"customer_matters": 2, "matter_documents": 1, "dead_letter_queue": 1}
    assert report["pitr_verified"] is False
    with psycopg.connect(isolated_database) as conn:
        assert conn.execute("SELECT count(*) FROM customer_matters").fetchone()[0] == 2
    with pytest.raises(ValueError, match="disposable"):
        restore_table_data(isolated_database, tmp_path / "backup")


def test_pooled_concurrent_tenants_and_aborted_transactions_do_not_leak(isolated_database):
    with psycopg.connect(isolated_database) as conn:
        conn.execute("ALTER TABLE customer_matters ENABLE ROW LEVEL SECURITY")
        conn.execute("ALTER TABLE customer_matters FORCE ROW LEVEL SECURITY")
        conn.execute("GRANT SELECT ON customer_matters TO fintax_app")
        conn.execute("CREATE POLICY tenant ON customer_matters USING (tenant_id = NULLIF(current_setting('app.current_tenant_id',true),''))")
    def configure(conn):
        conn.execute("SET ROLE fintax_app")
    with ConnectionPool(isolated_database, min_size=1, max_size=2, kwargs={"autocommit": True}, configure=configure) as pool:
        def query(index):
            tenant, matter = ("tenant-A", "mA") if index % 2 else ("tenant-B", "mB")
            scope = PermissionScope(tenant, "user", allowed_matter_ids=(matter,))
            with request_connection(pool, scope, matter) as conn:
                return conn.execute("SELECT tenant_id FROM customer_matters").fetchall() == [(tenant,)]
        with ThreadPoolExecutor(max_workers=8) as executor:
            assert all(executor.map(query, range(40)))
        with pytest.raises(psycopg.errors.DivisionByZero):
            with request_connection(pool, PermissionScope("tenant-A", "user")) as conn:
                conn.execute("SELECT 1/0")
        with pool.connection() as conn:
            assert conn.execute("SELECT current_setting('app.current_tenant_id',true)").fetchone()[0] in ("", None)
            assert conn.execute("SELECT tenant_id FROM customer_matters").fetchall() == []
    with psycopg.connect(isolated_database, autocommit=True) as admin:
        with pytest.raises(RuntimeError, match="unprivileged"):
            check_connection(admin)
