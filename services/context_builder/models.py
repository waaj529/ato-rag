"""Typed parent-context records for Phase 4."""

from dataclasses import dataclass


@dataclass(frozen=True)
class ContextSettings:
    token_budget: int = 12_000
    max_evidence: int = 10
    version: str = "phase4-context-v1"


@dataclass(frozen=True)
class ParentRecord:
    parent_id: str
    document_id: str
    version_id: str
    source_class: str
    canonical_reference_id: str | None
    authority_rank: int | None
    title: str
    source_url: str
    heading_path: tuple[str, ...]
    source_locator: dict
    content: str
    text_units: int


@dataclass(frozen=True)
class EvidenceUnit:
    evidence_id: str
    parent_id: str
    document_id: str
    version_id: str
    authority_class: str
    citation_label: str
    title: str
    source_url: str
    heading_path: tuple[str, ...]
    parent_locator: dict
    triggering_child_locator: dict
    retrieval_reason: str
    reranker_score: float
    text: str
    text_units: int


@dataclass(frozen=True)
class ContextPackage:
    query: str
    evidence: tuple[EvidenceUnit, ...]
    total_text_units: int
    settings_version: str
