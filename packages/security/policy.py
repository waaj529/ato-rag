"""Scope and safety policy evaluation gate prior to retrieval."""

from dataclasses import dataclass
import re
from typing import Sequence

from packages.telemetry import span
from .injection import detect_prompt_injection

_TAX_EVASION_PATTERNS: tuple[re.Pattern, ...] = (
    re.compile(r"\b(hide\s+(cash|income)|off\s+the\s+books|launder|evade\s+tax|tax\s+evasion)\b", re.I),
    re.compile(r"\b(disregard\s+all\s+ato|unreported\s+cash\s+economy)\b", re.I),
)

_MALFORMED_PATTERNS: tuple[re.Pattern, ...] = (
    re.compile(r"(\?{2,}|:{2,}|;{2,}|\${2,}|@{2,})"),
)


@dataclass(frozen=True)
class PolicyDecision:
    passed: bool
    code: str
    reason: str


class ScopeSafetyPolicyGate:
    """Evaluates query safety, prompt injection and evasion before retrieval."""

    def evaluate(self, query: str) -> PolicyDecision:
        with span("scope_safety_policy_evaluation"):
            clean_q = query.strip()

            # Malformed syntax check
            alpha_words = re.findall(r"[a-z]{2,}", clean_q.casefold())
            is_alphanumeric_ratio = (sum(c.isalnum() for c in clean_q) / max(1, len(clean_q)))
            if not alpha_words or is_alphanumeric_ratio < 0.35:
                return PolicyDecision(False, "MALFORMED_INPUT", "Query lacks substantive semantic tokens or readable text.")

            for pat in _MALFORMED_PATTERNS:
                if pat.search(clean_q):
                    return PolicyDecision(False, "MALFORMED_SYNTAX", "Query contains malformed punctuation symbols; unparseable input.")

            # Prompt injection check
            has_injection, markers = detect_prompt_injection(clean_q)
            if has_injection:
                return PolicyDecision(False, "PROMPT_INJECTION", f"Adversarial instruction override detected: {', '.join(markers)}")

            # Illicit tax evasion check
            for pat in _TAX_EVASION_PATTERNS:
                if pat.search(clean_q):
                    return PolicyDecision(False, "TAX_EVASION_REFUSAL", "Query solicits unlawful tax evasion or fraudulent non-compliance.")

            return PolicyDecision(True, "POLICY_PASSED", "Query complies with product and safety policies.")
