"""Deterministic parent expansion, merging and context budgeting."""

from packages.telemetry import span
from services.reranking import RerankingResult

from .models import ContextPackage, ContextSettings, EvidenceUnit, ParentRecord


class ParentProvider:
    def parents(self, parent_ids: tuple[str, ...]) -> dict[str, ParentRecord]:
        raise NotImplementedError


class ContextBuilder:
    def __init__(self, provider: ParentProvider,
                 settings: ContextSettings = ContextSettings()) -> None:
        self.provider = provider
        self.settings = settings

    def build(self, result: RerankingResult) -> ContextPackage:
        with span("parent_expansion", {"child_count": len(result.children)}):
            parent_ids = tuple(dict.fromkeys(
                child.candidate.parent_chunk_id for child in result.children
            ))
            parents = self.provider.parents(parent_ids)
        with span("context_build", {"token_budget": self.settings.token_budget}):
            evidence: list[EvidenceUnit] = []
            used: set[str] = set()
            total = 0
            for child in result.children:
                parent_id = child.candidate.parent_chunk_id
                if parent_id in used or parent_id not in parents:
                    continue
                parent = parents[parent_id]
                if evidence and total + parent.text_units > self.settings.token_budget:
                    continue
                reason = "+".join(sorted(child.candidate.retrieved.ranks)) + "+reranker"
                label = parent.canonical_reference_id or parent.title
                evidence.append(EvidenceUnit(
                    evidence_id=f"E{len(evidence) + 1}", parent_id=parent.parent_id,
                    document_id=parent.document_id, version_id=parent.version_id,
                    authority_class=parent.source_class, citation_label=label,
                    title=parent.title, source_url=parent.source_url,
                    heading_path=parent.heading_path, parent_locator=parent.source_locator,
                    triggering_child_locator=child.candidate.retrieved.candidate.source_locator,
                    retrieval_reason=reason, reranker_score=child.reranker_score,
                    text=parent.content, text_units=parent.text_units,
                ))
                used.add(parent_id)
                total += parent.text_units
                if len(evidence) == self.settings.max_evidence:
                    break
            return ContextPackage(result.query, tuple(evidence), total, self.settings.version)
