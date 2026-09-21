"""Document metadata inherited by every self-contained child chunk."""

from typing import Any


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
    }
