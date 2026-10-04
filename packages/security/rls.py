"""Fail-closed PostgreSQL Row-Level Security session context management."""

from contextlib import contextmanager
from typing import Iterator

import psycopg


def _recover_aborted_transaction(connection: psycopg.Connection) -> None:
    if connection.info.transaction_status == psycopg.pq.TransactionStatus.INERROR:
        connection.rollback()


def set_tenant_session(connection: psycopg.Connection, tenant_id: str | None) -> None:
    """Enter the application role before allowing any tenant query."""
    val = tenant_id.strip() if tenant_id else ""
    try:
        _recover_aborted_transaction(connection)
        connection.execute("SET ROLE fintax_app")
        connection.execute("SELECT set_config('app.current_tenant_id', %s, false)", (val,))
    except Exception:
        # An uncertain role or tenant state must never return to a pool.
        connection.close()
        raise


def reset_tenant_session(connection: psycopg.Connection) -> None:
    """Clear tenant context; discard connections whose isolation cannot be restored."""
    try:
        _recover_aborted_transaction(connection)
        connection.execute("SELECT set_config('app.current_tenant_id', '', false)")
        connection.execute("SET ROLE fintax_app")
    except Exception:
        connection.close()
        raise


@contextmanager
def scoped_tenant_connection(
    connection: psycopg.Connection, tenant_id: str | None
) -> Iterator[psycopg.Connection]:
    """Apply tenant context and fail closed on either entry or cleanup failure."""
    set_tenant_session(connection, tenant_id)
    try:
        yield connection
    finally:
        reset_tenant_session(connection)
