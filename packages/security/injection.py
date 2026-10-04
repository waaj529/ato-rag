"""Prompt-injection sanitization, boundary defense and payload detection."""

import re

INJECTION_PATTERNS: tuple[re.Pattern, ...] = (
    re.compile(r"ignore\s+(all\s+)?(previous|prior)\s+instructions", re.IGNORECASE),
    re.compile(r"(system\s+(prompt\s+)?|developer\s+mode\s+)(override|bypass)", re.IGNORECASE),
    re.compile(r"(print|reveal|expose|dump)\s+(api_key|secret|credential|token|password)", re.IGNORECASE),
    re.compile(r"(exfiltrate|send\s+data\s+to|curl|wget)\s+https?://", re.IGNORECASE),
    re.compile(r"you\s+are\s+now\s+an\s+unrestricted", re.IGNORECASE),
    re.compile(r"disregard\s+(all\s+)?(legal|tax|system)\s+(rules|law|instructions)", re.IGNORECASE),
)


def detect_prompt_injection(text: str) -> tuple[bool, list[str]]:
    """Scan input or retrieved text for known adversarial injection patterns."""
    matched = []
    for pattern in INJECTION_PATTERNS:
        match = pattern.search(text)
        if match:
            matched.append(match.group(0))
    return (len(matched) > 0, matched)


def sanitize_input_text(text: str) -> str:
    """Neutralize command sequences and control characters from user text."""
    if not isinstance(text, str):
        return ""
    sanitized = re.sub(r"[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]", "", text)
    return sanitized.strip()


def wrap_untrusted_evidence(evidence_id: str, title: str, text: str) -> str:
    """Wrap retrieved passage in strict immutable data boundaries."""
    clean_text = sanitize_input_text(text)
    is_suspicious, patterns = detect_prompt_injection(clean_text)
    warning_header = ""
    if is_suspicious:
        warning_header = f"<!-- WARNING: Adversarial markers detected: {', '.join(patterns)} -->\n"

    return (
        f'<untrusted_legal_evidence id="{evidence_id}" title="{title}">\n'
        f"{warning_header}"
        f"{clean_text}\n"
        f"</untrusted_legal_evidence>"
    )
