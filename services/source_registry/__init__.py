"""Source configuration, identifier, and authority rules."""

from .authority import normalize_authority
from .identifiers import normalize_document, resolve_citation
from .scope_gate import CorpusScopeGate, ScopeDecision, ScopeStatus

__all__ = [
    "CorpusScopeGate",
    "ScopeDecision",
    "ScopeStatus",
    "normalize_authority",
    "normalize_document",
    "resolve_citation",
]
