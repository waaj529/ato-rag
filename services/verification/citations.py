"""Deterministic citation resolution from stored document and version metadata."""

from typing import Sequence

from services.context_builder import ContextPackage, EvidenceUnit
from .models import CitationObject


class CitationResolver:
    def __init__(self, default_jurisdiction: str = "AU-COMMONWEALTH") -> None:
        self.default_jurisdiction = default_jurisdiction

    def resolve(
        self, evidence_ids: Sequence[str], context: ContextPackage
    ) -> tuple[CitationObject, ...]:
        by_id = {u.evidence_id: u for u in context.evidence}
        citations: list[CitationObject] = []
        seen: set[str] = set()
        for idx, eid in enumerate(evidence_ids, 1):
            if eid in seen or eid not in by_id:
                continue
            unit: EvidenceUnit = by_id[eid]
            citations.append(CitationObject(
                citation_id=f"cit_{idx:02d}",
                document_id=unit.document_id,
                document_version_id=unit.version_id,
                evidence_id=unit.evidence_id,
                display=unit.citation_label or unit.title,
                jurisdiction=self.default_jurisdiction,
                locator=unit.triggering_child_locator or unit.parent_locator or {},
                official_url=unit.source_url,
                internal_snapshot_url=f"/data/source_snapshots/documents/{unit.document_id}.json",
            ))
            seen.add(eid)
        return tuple(citations)
