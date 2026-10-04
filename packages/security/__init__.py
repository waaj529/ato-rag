"""Production security, authorization, isolation, and resilience (Phase 6)."""

from .audit import audit_security_controls
from .dlq import DeadLetterQueue
from .headers import get_security_headers, sanitize_output
from .identity import (
    DEFAULT_PUBLIC_SCOPE,
    PermissionScope,
    UserIdentity,
    authenticate_bearer_token,
    create_permission_scope,
)
from .injection import (
    detect_prompt_injection,
    sanitize_input_text,
    wrap_untrusted_evidence,
)
from .privacy import redact_text, sanitize_trace_metadata, stable_hash
from .ratelimit import (
    RateLimiter,
    RateLimitExceededError,
    SpendBudgetManager,
    SpendLimitExceededError,
)
from .resilience import (
    CircuitBreaker,
    CircuitBreakerOpenError,
    CircuitState,
    bounded_retry,
)
from .rls import (
    reset_tenant_session,
    scoped_tenant_connection,
    set_tenant_session,
)
from .scope import (
    MissingScopeError,
    PermissionDeniedError,
    SecurityError,
    enforce_request_scope,
    get_current_scope,
    resolve_and_enforce_scope,
    scope_context,
)
from .policy import PolicyDecision, ScopeSafetyPolicyGate
from .secrets import SecretsProvider, get_secret

__all__ = [
    "PolicyDecision",
    "ScopeSafetyPolicyGate",
    "CircuitBreaker",
    "CircuitBreakerOpenError",
    "CircuitState",
    "DEFAULT_PUBLIC_SCOPE",
    "DeadLetterQueue",
    "MissingScopeError",
    "PermissionDeniedError",
    "PermissionScope",
    "RateLimitExceededError",
    "RateLimiter",
    "SecretsProvider",
    "SecurityError",
    "SpendBudgetManager",
    "SpendLimitExceededError",
    "UserIdentity",
    "audit_security_controls",
    "authenticate_bearer_token",
    "bounded_retry",
    "create_permission_scope",
    "detect_prompt_injection",
    "enforce_request_scope",
    "get_current_scope",
    "get_secret",
    "get_security_headers",
    "redact_text",
    "reset_tenant_session",
    "resolve_and_enforce_scope",
    "sanitize_input_text",
    "sanitize_output",
    "sanitize_trace_metadata",
    "scope_context",
    "scoped_tenant_connection",
    "set_tenant_session",
    "stable_hash",
    "wrap_untrusted_evidence",
]
