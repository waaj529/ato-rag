"""Classification-aware telemetry redaction and privacy policy enforcement."""

import hashlib

PUBLIC_CLASSIFICATIONS: frozenset[str] = frozenset({"PUBLIC_OFFICIAL", "PUBLIC_SECONDARY"})
CONFIDENTIAL_CLASSIFICATIONS: frozenset[str] = frozenset({
    "CUSTOMER_CONFIDENTIAL",
    "PERSONAL_INFORMATION",
    "SENSITIVE_INFORMATION",
    "PRIVILEGED_OR_RESTRICTED",
})


def stable_hash(*parts: str) -> str:
    """Deterministic SHA-256 hash for domain identity components."""
    return hashlib.sha256("\x1f".join(parts).encode()).hexdigest()


def redact_text(text: str, classification: str) -> str:
    """Redact raw text if classification is confidential, preserving stable content hash."""
    if classification in PUBLIC_CLASSIFICATIONS:
        return text
    sha = hashlib.sha256(text.encode()).hexdigest()[:16]
    return f"[REDACTED_CONTENT:sha256={sha}:len={len(text)}]"


def sanitize_trace_metadata(metadata: dict, classification: str) -> dict:
    """Filter observation metadata based on data classification policy."""
    if classification in PUBLIC_CLASSIFICATIONS:
        return dict(metadata)

    sanitized = {}
    for key, val in metadata.items():
        # Keep numeric metrics, identifiers and token counts intact
        if key in {
            "candidate_count_in", "candidate_count_out", "pre_rerank_ranks",
            "post_rerank_ranks", "scores", "input_tokens", "output_tokens",
            "evidence_support", "answer_completeness", "relevance",
            "unsupported_claim_risk", "overall_score",
        }:
            sanitized[key] = val
        elif isinstance(val, (int, float, bool)):
            sanitized[key] = val
        elif isinstance(val, str):
            sanitized[key] = redact_text(val, classification)
        else:
            sanitized[key] = "[REDACTED_COMPLEX_DATA]"
    return sanitized
