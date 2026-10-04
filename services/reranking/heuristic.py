"""Local lexical reranking experiment; not a Jev integration or model call."""

import re
from typing import Sequence

from .models import HydratedCandidate, RelevanceSignals, RerankedChild

_AUTHORITY_WEIGHTS: dict[str, float] = {
    "legislation": 1.0,
    "statutory_rule": 0.95,
    "court_decision": 0.90,
    "public_ruling": 0.85,
    "practical_compliance_guideline": 0.75,
    "ato_determination": 0.80,
    "interpretative_decision": 0.70,
    "guidance": 0.60,
}
_WORDS = re.compile(r"[a-z0-9]{2,}")
_LEGAL_MARKERS = re.compile(r"\b(section|subsection|paragraph|deduct|assess|income|tax|capital|rate)\b", re.I)


class HeuristicReranker:
    def __init__(self, revision: str = "2026-v1") -> None:
        self._revision = revision

    @property
    def provider_name(self) -> str:
        return "local-heuristic"

    @property
    def model_name(self) -> str:
        return "heuristic-reranker"

    @property
    def revision(self) -> str:
        return self._revision

    def rerank_candidates(
        self, query: str, candidates: Sequence[HydratedCandidate], top_n: int
    ) -> tuple[tuple[RerankedChild, ...], int]:
        if not candidates:
            return (), 0
        q_terms = set(_WORDS.findall(query.casefold()))
        scored: list[tuple[HydratedCandidate, RelevanceSignals, float]] = []
        tokens = 0
        for cand in candidates:
            tokens += len(cand.content_for_reranking.split())
            signals = self._evaluate_signals(q_terms, cand)
            scored.append((cand, signals, signals.composite_score()))
        scored.sort(key=lambda item: item[2], reverse=True)
        selected = scored[:top_n]
        children = tuple(
            RerankedChild(cand, score, rank, signals)
            for rank, (cand, signals, score) in enumerate(selected, 1)
        )

        return children, tokens

    def _evaluate_signals(self, q_terms: set[str], cand: HydratedCandidate) -> RelevanceSignals:
        c_terms = set(_WORDS.findall(cand.content.casefold()))
        h_terms = set(_WORDS.findall(cand.contextual_header.casefold()))
        matched = len(q_terms & (c_terms | h_terms))
        relevant = min(1.0, (matched / max(1, len(q_terms))) * 1.2)
        words = len(cand.content.split())
        markers = len(_LEGAL_MARKERS.findall(cand.content))
        answer_bearing = min(1.0, 0.4 + (markers / max(1, words)) * 3.0)
        if words < 15:
            answer_bearing *= 0.5
        authority_fit = _AUTHORITY_WEIGHTS.get(cand.source_class, 0.70)
        temporal_fit = 0.95 if "1997" in cand.content or "202" in cand.content else 0.85
        return RelevanceSignals(
            relevant=round(relevant, 4),
            answer_bearing=round(answer_bearing, 4),
            authority_fit=round(authority_fit, 4),
            temporal_fit=round(temporal_fit, 4),
        )

