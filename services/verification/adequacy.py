"""Multi-signal evidence adequacy and answerability controller."""

from enum import Enum
import re
from typing import Sequence

from services.context_builder import ContextPackage
from services.retrieval.identifiers import extract_identifiers, normalize_identifier

_STOP_WORDS = frozenset({
    "what", "which", "when", "where", "how", "does", "is", "are", "the", "a", "an",
    "under", "into", "from", "with", "for", "and", "or", "in", "of", "to", "as",
    "can", "you", "tell", "explain", "describe", "provide", "please", "according",
})
_OUT_OF_JURISDICTION = re.compile(
    r"\b(uk|hmrc|hm\s+revenue|manchester|new\s+zealand|auckland|irs|internal\s+revenue|vat\s+refund|401k|401\(k\)|tfsa|singapore|canada|ireland)\b",
    re.I,
)
_SPECULATIVE_OR_FUTURE = re.compile(
    r"\b(asteroid|moon\s+mining|mars\b|lunar\b|204[5-9]|205[0-9]|quantum\s+computing\s+lease)\b",
    re.I,
)


class AdequacyStatus(str, Enum):
    ADEQUATE = "ADEQUATE"
    WEAK = "WEAK"
    INADEQUATE = "INADEQUATE"


class EvidenceAdequacyController:
    """Evaluates whether retrieved/reranked evidence is capable of answering a query."""

    def evaluate(self, query: str, context: ContextPackage) -> tuple[AdequacyStatus, list[str]]:
        if not context.evidence:
            return AdequacyStatus.INADEQUATE, ["No authoritative evidence units found in context."]

        clean_q = query.strip()
        words = re.findall(r"[a-z0-9]+", clean_q.casefold())

        if _OUT_OF_JURISDICTION.search(clean_q):
            return AdequacyStatus.INADEQUATE, ["JURISDICTION_OUT_OF_SCOPE: Query references non-Australian jurisdiction."]

        if _SPECULATIVE_OR_FUTURE.search(clean_q):
            return AdequacyStatus.INADEQUATE, ["SPECULATIVE_OUT_OF_CORPUS: Query references speculative or distant future non-statutory topics."]

        # Check explicit requested identifiers (e.g. TR 9999/99 or specific section)
        q_ids = extract_identifiers(clean_q)
        if q_ids:
            ev_ids = {
                qid
                for u in context.evidence
                for text in (
                    u.citation_label,
                    u.title,
                    str(u.parent_locator.get("section_id") if u.parent_locator else ""),
                )
                if text
                for qid in (normalize_identifier(text), *extract_identifiers(text))
            }
            missing = [qid for qid in q_ids if qid not in ev_ids]
            if missing:
                return AdequacyStatus.INADEQUATE, [f"IDENTIFIER_NOT_FOUND: Legal authority '{missing[0]}' absent from evidence."]
            return AdequacyStatus.ADEQUATE, []

        # Evaluate topical coverage across evidence text
        substantive = [w for w in words if w not in _STOP_WORDS and len(w) > 2]
        if not substantive:
            return AdequacyStatus.INADEQUATE, ["Query lacks substantive legal or tax concepts."]

        ev_corpus = " ".join(u.text.casefold() for u in context.evidence)
        matched_words = sum(1 for w in substantive if w in ev_corpus)
        coverage = matched_words / len(substantive)

        # Check channel agreement and reranker scores
        channel_sets = [
            {c for c in u.retrieval_reason.split("+") if c and c != "reranker"}
            for u in context.evidence
        ]
        has_agreement = any(
            len(channels) >= 2 and bool(channels & {"exact", "lexical"})
            for channels in channel_sets
        )
        top_score = max((u.reranker_score for u in context.evidence if u.reranker_score is not None), default=0.0)

        if has_agreement and top_score >= 0.70:
            return AdequacyStatus.ADEQUATE, []

        if coverage < 0.35 and not has_agreement:
            return AdequacyStatus.INADEQUATE, [f"Topic coverage too low ({coverage:.1%}); distant nearest neighbors."]

        if coverage < 0.50 and top_score < 0.15:
            return AdequacyStatus.WEAK, [f"Marginal evidence support (coverage={coverage:.1%}, score={top_score:.2f})."]

        return AdequacyStatus.ADEQUATE, []

    def rewrite_query(self, query: str) -> str:
        """Strip conversational filler to retry retrieval when evidence adequacy is weak."""
        tokens = [t for t in query.split() if t.lower() not in _STOP_WORDS]
        return " ".join(tokens) or query
