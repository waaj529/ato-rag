"""Grounded generation and repair adapters for Phase 5."""

import re
from typing import Sequence

from services.context_builder import ContextPackage
from .models import Claim, StructuredAnswer

_SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s+")


class ExtractiveGenerator:
    def __init__(self, model_name: str = "extractive-fixture-v1",
                 provider_name: str = "local-extractive", revision: str = "2026-v1") -> None:
        self._model_name = model_name
        self._provider_name = provider_name
        self._revision = revision

    @property
    def provider_name(self) -> str:
        return self._provider_name

    @property
    def model_name(self) -> str:
        return self._model_name

    @property
    def revision(self) -> str:
        return self._revision

    def generate_answer(
        self, query: str, context: ContextPackage, task: str = "generate"
    ) -> tuple[StructuredAnswer, int, int]:
        in_tokens = len(query.split()) + context.total_text_units
        if not context.evidence:
            return (
                StructuredAnswer(
                    answer_markdown="Under Australian taxation law, insufficient authoritative evidence is available in the corpus to support an answer to this query.",
                    claims=(),
                    limitations=("No authoritative statutory or administrative evidence found.",),
                    needs_human_review=True,
                ),
                in_tokens,
                25,
            )

        claims: list[Claim] = []
        answer_parts: list[str] = [f"Based on authoritative Australian tax law regarding '{query}':\n"]
        for idx, unit in enumerate(context.evidence[:4], 1):
            sentences = [s.strip() for s in _SENTENCE_SPLIT.split(unit.text) if len(s.strip()) > 30]
            lead = sentences[0] if sentences else unit.text[:200]
            claim_id = f"C{idx}"
            claims.append(Claim(claim_id=claim_id, text=lead, evidence_ids=(unit.evidence_id,)))
            answer_parts.append(f"- **{unit.citation_label}**: {lead} [{unit.evidence_id}]")

        answer_parts.append(
            "\n*Note: Citations above reflect the governing legislative and administrative authorities in the official corpus.*"
        )
        answer_markdown = "\n".join(answer_parts)
        limitations = (
            "Applies to Commonwealth taxation jurisdiction under current legislation.",
            "Specific taxpayer circumstances may require a formal private ruling.",
        )
        out_tokens = len(answer_markdown.split())
        return (
            StructuredAnswer(
                answer_markdown=answer_markdown,
                claims=tuple(claims),
                limitations=limitations,
                needs_human_review=False,
            ),
            in_tokens,
            out_tokens,
        )


class RepairGenerator:
    def repair(
        self, draft: StructuredAnswer, errors: Sequence[str], context: ContextPackage
    ) -> StructuredAnswer:
        # Citation membership cannot establish semantic support. Preserve failed
        # claims so the final validator rejects them instead of inventing support.
        return StructuredAnswer(
            answer_markdown=draft.answer_markdown,
            claims=draft.claims,
            limitations=draft.limitations + tuple(f"Unresolved validation error: {err}" for err in errors),
            needs_human_review=draft.needs_human_review or bool(errors),
        )
