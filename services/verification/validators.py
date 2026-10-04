"""Deterministic validation pipeline for Phase 5 grounded answers."""

from services.context_builder import ContextPackage
from services.generation import StructuredAnswer
from .citations import CitationResolver
from .models import EvidenceState, ValidationResult


class DeterministicValidator:
    def __init__(self, resolver: CitationResolver | None = None) -> None:
        self.resolver = resolver or CitationResolver()

    def validate(self, answer: StructuredAnswer, context: ContextPackage) -> ValidationResult:
        errors: list[str] = []
        supplied_ids = {u.evidence_id: u for u in context.evidence}

        if not isinstance(answer.answer_markdown, str) or not answer.answer_markdown.strip():
            errors.append("Schema violation: answer_markdown is empty or not a string.")

        if not answer.claims:
            errors.append("Generated answer has no verifiable material claims.")
        if len(supplied_ids) != len(context.evidence):
            errors.append("Context contains ambiguous duplicate evidence IDs.")
        claim_ids = [claim.claim_id for claim in answer.claims]
        if any(not cid.strip() for cid in claim_ids) or len(set(claim_ids)) != len(claim_ids):
            errors.append("Material claim IDs must be non-empty and unique.")

        all_claimed_ids: list[str] = []
        for claim in answer.claims:
            if not claim.text.strip():
                errors.append(f"Material claim {claim.claim_id} text is empty.")
            if not claim.evidence_ids:
                errors.append(f"Material claim {claim.claim_id} lacks supporting evidence IDs.")
            for eid in claim.evidence_ids:
                all_claimed_ids.append(eid)
                if eid not in supplied_ids:
                    errors.append(f"Claim {claim.claim_id} references unsupplied evidence ID: {eid}")
                else:
                    unit = supplied_ids[eid]
                    if not unit.source_url or not unit.parent_id:
                        errors.append(f"Evidence {eid} missing source URL or parent lineage.")
                    if not unit.document_id or not unit.version_id:
                        errors.append(f"Evidence {eid} missing immutable document or version ID.")
                    if not unit.triggering_child_locator and not unit.parent_locator:
                        errors.append(f"Evidence {eid} missing resolvable locator metadata.")

        if not supplied_ids and answer.claims:
            errors.append("Answer makes claims but no context evidence was supplied.")

        resolved_citations = self.resolver.resolve(all_claimed_ids, context)
        passed = len(errors) == 0

        if not context.evidence:
            state = EvidenceState.INSUFFICIENT_EVIDENCE
        elif passed and answer.claims:
            state = EvidenceState.SUPPORTED
        elif passed and not answer.claims:
            state = EvidenceState.INSUFFICIENT_EVIDENCE
        elif any(eid in supplied_ids for eid in all_claimed_ids):
            state = EvidenceState.PARTIALLY_SUPPORTED
        else:
            state = EvidenceState.INSUFFICIENT_EVIDENCE

        return ValidationResult(
            passed=passed,
            errors=tuple(errors),
            evidence_state=state,
            resolved_citations=resolved_citations,
        )
