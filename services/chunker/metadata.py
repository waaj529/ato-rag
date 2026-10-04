"""Document metadata inherited by every self-contained child chunk."""

from typing import Any, Sequence


def inherited_chunk_metadata(document: dict[str, Any]) -> dict[str, Any]:
    classification = document.get("classification") or {}
    return {
        "title": document.get("title"),
        "source_url": document.get("source_url"),
        "publisher": document.get("publisher"),
        "corpus": classification.get("corpus"),
        "source_class": classification.get("source_class"),
        "applicable_periods": classification.get("applicable_periods") or [],
        "historical_guidance": classification.get("historical_guidance", False),
        "binding_effect": classification.get("binding_effect"),
        "authority_rank": classification.get("authority_rank"),
        "page_status": classification.get("page_status"),
        "canonical_reference_id": document.get("canonical_reference_id"),
        "canonical_reference": document.get("canonical_reference"),
    }


def contextual_header(document: dict[str, Any], path: Sequence[str]) -> str:
    classification = document.get("classification") or {}
    version = document.get("version") or {}
    periods = ", ".join(classification.get("applicable_periods") or []) or "not specified"
    heading = " > ".join(str(item) for item in path if item) or document.get("title", "")
    lines = [
        "[JURISDICTION: Commonwealth of Australia]",
        f"[SOURCE: {document.get('publisher') or 'Unknown'}]",
        f"[DOCUMENT: {document.get('title') or 'Untitled'}]",
        f"[VERSION: {version.get('version_id') or 'unknown'}]",
        f"[APPLICABLE-PERIOD: {periods}]",
        f"[PATH: {heading}]",
        f"[AUTHORITY: {classification.get('source_class') or 'unknown'}]",
    ]
    if document.get("canonical_reference_id"):
        lines.append(f"[CITATION: {document['canonical_reference_id']}]")
    return "\n".join(lines)
