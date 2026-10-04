"""Typed verification models, citation schemas and evidence states."""

from dataclasses import dataclass
from enum import Enum


class EvidenceState(str, Enum):
    SUPPORTED = "SUPPORTED"
    PARTIALLY_SUPPORTED = "PARTIALLY_SUPPORTED"
    CONFLICTING_AUTHORITIES = "CONFLICTING_AUTHORITIES"
    INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"
    OUT_OF_SCOPE = "OUT_OF_SCOPE"


@dataclass(frozen=True)
class CitationObject:
    citation_id: str
    document_id: str
    document_version_id: str
    evidence_id: str
    display: str
    jurisdiction: str
    locator: dict
    official_url: str
    internal_snapshot_url: str
    effective_date: str | None = None


@dataclass(frozen=True)
class ValidationResult:
    passed: bool
    errors: tuple[str, ...]
    evidence_state: EvidenceState
    resolved_citations: tuple[CitationObject, ...]


@dataclass(frozen=True)
class JudgeDecision:
    evidence_support: float
    answer_completeness: float
    relevance: float
    unsupported_claim_risk: float
    evaluation_kind: str = "heuristic_proxy"

    @property
    def overall_score(self) -> float:
        return round(
            0.40 * self.evidence_support
            + 0.30 * self.answer_completeness
            + 0.20 * self.relevance
            + 0.10 * (1.0 - self.unsupported_claim_risk),
            4,
        )
