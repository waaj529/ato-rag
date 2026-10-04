"""Mandatory permission scope enforcement and fail-closed security gates."""

from contextlib import contextmanager
from contextvars import ContextVar
from typing import Iterator

from .identity import DEFAULT_PUBLIC_SCOPE, PermissionScope

_ACTIVE_SCOPE: ContextVar[PermissionScope | None] = ContextVar("_ACTIVE_SCOPE", default=None)


class SecurityError(Exception):
    """Base security error."""


class MissingScopeError(SecurityError):
    """Raised when mandatory permission_scope is absent."""


class PermissionDeniedError(SecurityError):
    """Raised when request violates tenant, matter or classification boundary."""


def get_current_scope() -> PermissionScope | None:
    return _ACTIVE_SCOPE.get()


@contextmanager
def scope_context(scope: PermissionScope) -> Iterator[PermissionScope]:
    token = _ACTIVE_SCOPE.set(scope)
    try:
        yield scope
    finally:
        _ACTIVE_SCOPE.reset(token)


def enforce_request_scope(
    scope: PermissionScope | None,
    target_tenant_id: str | None = None,
    matter_id: str | None = None,
    classification: str = "PUBLIC_OFFICIAL",
) -> None:
    """Enforce fail-closed permission scope on every retrieval and answer request."""
    if scope is None:
        raise MissingScopeError("Request failed closed: permission_scope is mandatory.")

    if not isinstance(scope, PermissionScope):
        raise MissingScopeError("Invalid permission_scope object.")

    if not scope.tenant_id or not scope.tenant_id.strip():
        raise MissingScopeError("Permission scope must specify non-empty tenant_id.")

    if target_tenant_id is not None and scope.tenant_id != target_tenant_id:
        raise PermissionDeniedError(
            f"Cross-tenant access violation: scope tenant '{scope.tenant_id}' "
            f"cannot access target tenant '{target_tenant_id}'."
        )

    if matter_id is not None and not scope.allows_matter(matter_id):
        raise PermissionDeniedError(
            f"Matter access denied: tenant '{scope.tenant_id}' user '{scope.user_id}' "
            f"cannot access matter '{matter_id}'."
        )

    if not scope.allows_classification(classification):
        raise PermissionDeniedError(
            f"Classification boundary violation: scope forbids '{classification}'."
        )


def resolve_and_enforce_scope(
    scope: PermissionScope | None,
    target_tenant_id: str | None = None,
    matter_id: str | None = None,
    classification: str = "PUBLIC_OFFICIAL",
    allow_default: bool = True,
) -> PermissionScope:
    effective = scope or get_current_scope()
    if effective is None and allow_default:
        effective = DEFAULT_PUBLIC_SCOPE
    enforce_request_scope(effective, target_tenant_id, matter_id, classification)
    return effective
