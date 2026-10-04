"""Uncalibrated lexical evidence proxy; never a model call or factual accuracy grade."""

import re

from packages.telemetry import span
from services.context_builder import ContextPackage
from services.generation import StructuredAnswer
from .models import JudgeDecision

_WORDS = re.compile(r"[a-z0-9]{2,}")


class HeuristicEvidenceJudge:
    def __init__(self, revision: str = "2026-v1") -> None:
        self._revision = revision

    @property
    def provider_name(self) -> str:
        return "local-heuristic"

    @property
    def model_name(self) -> str:
        return "heuristic-evidence-judge"

    @property
    def revision(self) -> str:
        return self._revision

    def judge(
        self, query: str, answer: StructuredAnswer, context: ContextPackage
    ) -> JudgeDecision:
        with span("heuristic_evidence_judge", {"evaluation.kind": "heuristic_proxy"}):
            return self._evaluate_decision(query, answer, context)

    def _evaluate_decision(
        self, query: str, answer: StructuredAnswer, context: ContextPackage
    ) -> JudgeDecision:
        if not context.evidence:
            relevance = 1.0 if not answer.claims else 0.5
            return JudgeDecision(evidence_support=1.0, answer_completeness=1.0, relevance=relevance, unsupported_claim_risk=0.0)

        q_terms = set(_WORDS.findall(query.casefold()))
        a_terms = set(_WORDS.findall(answer.answer_markdown.casefold()))
        relevance = min(1.0, len(q_terms & a_terms) / max(1, len(q_terms)))

        ev_by_id = {u.evidence_id: u for u in context.evidence}
        support_scores: list[float] = []
        for claim in answer.claims:
            c_terms = set(_WORDS.findall(claim.text.casefold()))
            claim_supports = []
            for eid in claim.evidence_ids:
                if eid in ev_by_id:
                    u_text = ev_by_id[eid].text.casefold()
                    u_terms = set(_WORDS.findall(u_text))
                    matches = sum(
                        1 for w in c_terms
                        if w in u_terms or (len(w) >= 4 and w[:4] in u_text)
                    )
                    match_ratio = matches / max(1, len(c_terms))
                    claim_supports.append(min(1.0, match_ratio * 1.5))
                else:
                    claim_supports.append(0.0)
            support_scores.append(max(claim_supports) if claim_supports else 0.0)

        avg_support = sum(support_scores) / max(1, len(support_scores)) if support_scores else 0.5
        completeness = 0.95 if answer.limitations and len(answer.claims) >= 1 else 0.70
        unsupported_risk = round(max(0.0, 1.0 - avg_support), 4)

        return JudgeDecision(
            evidence_support=round(avg_support, 4),
            answer_completeness=round(completeness, 4),
            relevance=round(relevance, 4),
            unsupported_claim_risk=unsupported_risk,
        )
