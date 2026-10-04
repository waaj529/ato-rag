"""Failed role and tenant transitions must never expose a usable connection."""

from types import SimpleNamespace
from unittest.mock import Mock

import psycopg
import pytest

from packages.security import scoped_tenant_connection


def _connection():
    connection = Mock()
    connection.info = SimpleNamespace(transaction_status=psycopg.pq.TransactionStatus.IDLE)
    return connection


@pytest.mark.parametrize("failure_at", [0, 1, 2, 3])
def test_failed_role_or_tenant_transition_closes_connection(failure_at):
    connection = _connection()
    connection.execute.side_effect = [None] * failure_at + [RuntimeError("transition failed")]
    entered = False
    with pytest.raises(RuntimeError, match="transition failed"):
        with scoped_tenant_connection(connection, "tenant-a"):
            entered = True
    assert entered is (failure_at >= 2)
    connection.close.assert_called_once()


def test_failed_aborted_transaction_recovery_closes_connection():
    connection = _connection()
    connection.info.transaction_status = psycopg.pq.TransactionStatus.INERROR
    connection.rollback.side_effect = RuntimeError("rollback failed")
    with pytest.raises(RuntimeError, match="rollback failed"):
        with scoped_tenant_connection(connection, "tenant-a"):
            pytest.fail("Request must not run after recovery failure")
    connection.close.assert_called_once()
    connection.execute.assert_not_called()
