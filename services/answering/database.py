"""Least-privilege pooled request transactions with transaction-local tenant context."""

from contextlib import contextmanager

from psycopg_pool import ConnectionPool
from packages.security import enforce_request_scope


def check_connection(conn):
    role = conn.execute("SELECT rolsuper, rolbypassrls, rolcreaterole, rolcreatedb FROM pg_roles WHERE rolname=current_user").fetchone()
    if not role or any(role):
        raise RuntimeError("API database credentials must be an unprivileged login")
    if conn.execute("SELECT current_user").fetchone()[0] != "fintax_api":
        raise RuntimeError("API database login must be fintax_api")
    leaked = conn.execute("SELECT current_setting('app.current_tenant_id', true)").fetchone()[0]
    if leaked:
        raise RuntimeError("Pooled connection retained tenant context")


def reset_connection(conn):
    conn.execute("DISCARD ALL")
    check_connection(conn)


def create_pool(dsn):
    return ConnectionPool(dsn, min_size=1, max_size=8, timeout=10, open=False,
                          kwargs={"autocommit": True}, configure=check_connection,
                          check=check_connection, reset=reset_connection)


@contextmanager
def request_connection(pool, scope, matter_id=None):
    enforce_request_scope(scope, matter_id=matter_id)
    with pool.connection() as conn:
        with conn.transaction():
            conn.execute("SELECT set_config('app.current_tenant_id', %s, true)", (scope.tenant_id,))
            conn.execute("SELECT set_config('app.current_matter_id', %s, true)", (matter_id or "",))
            conn.execute("SET LOCAL statement_timeout = '15s'")
            if matter_id is not None:
                found = conn.execute("SELECT 1 FROM customer_matters WHERE matter_id=%s", (matter_id,)).fetchone()
                if not found:
                    from packages.security import PermissionDeniedError
                    raise PermissionDeniedError("Matter is not accessible")
            yield conn
