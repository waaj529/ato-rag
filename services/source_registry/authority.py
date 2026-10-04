"""Evidence-based authority classification and lifecycle status normalization."""

import re
from urllib.parse import unquote


RULE_VERSION = "authority-classification-v1"
_WITHDRAWN_REFERENCE = re.compile(r"\b(?:TR|TD|LCR|GSTR|CR|PR|MT)\s+\d{2,4}/\d+W\b", re.I)
_DRAFT_REFERENCE = re.compile(r"\b(?:TR|TD|LCR|GSTR|CR|PR|MT)\s+\d{2,4}/D\d+\b", re.I)
_ACT_TITLE = re.compile(r"\bAct\s+(?:19|20)\d{2}\b", re.I)
_REGULATION_TITLE = re.compile(r"\bRegulations?\s+(?:19|20)\d{2}\b", re.I)


def _page_status(document: dict, classification: dict) -> str:
    explicit = str(classification.get("page_status") or "").casefold()
    evidence = " ".join((
        str(document.get("title") or ""),
        str(document.get("canonical_reference_id") or ""),
        unquote(str(document.get("source_url") or "")),
    ))
    if explicit == "withdrawn" or _WITHDRAWN_REFERENCE.search(evidence):
        return "withdrawn"
    if explicit == "draft" or "draft taxation ruling" in evidence.casefold() or _DRAFT_REFERENCE.search(evidence):
        return "draft"
    return str(classification.get("page_status") or "current")


def _source_class(document: dict, classification: dict) -> str | None:
    source_class = classification.get("source_class")
    if source_class != "primary_legislation":
        return source_class
    title = str(document.get("title") or "")
    url = unquote(str(document.get("source_url") or "")).casefold()
    if "docid=pac/" in url and _REGULATION_TITLE.search(title):
        return "commonwealth_regulation"
    if "docid=pac/" in url and _ACT_TITLE.search(title):
        return "commonwealth_statute"
    return "ato_public_guidance"


def normalize_authority(document: dict) -> dict:
    """Return a copy with one source taxonomy and fail-safe lifecycle authority."""
    if (document.get("classification_resolution") or {}).get("rule_version") == RULE_VERSION:
        return document
    original = dict(document.get("classification") or {})
    classification = dict(original)
    classification["source_class"] = _source_class(document, classification)
    classification["page_status"] = _page_status(document, classification)
    status = classification["page_status"]
    source_class = classification["source_class"]
    if status == "withdrawn":
        classification.update(binding_effect="withdrawn", authority_rank=90)
    elif status == "draft":
        classification.update(binding_effect="non_binding_draft", authority_rank=80)
    elif source_class in {"commonwealth_statute", "commonwealth_regulation"}:
        classification.update(binding_effect="binding_law", authority_rank=10)
    elif source_class == "ato_public_guidance":
        classification.update(binding_effect="non_binding_guidance", authority_rank=40)
    normalized = dict(document)
    normalized["classification"] = classification
    normalized["classification_resolution"] = {
        "original_source_class": original.get("source_class"),
        "original_page_status": original.get("page_status"),
        "original_binding_effect": original.get("binding_effect"),
        "original_authority_rank": original.get("authority_rank"),
        "rule_version": RULE_VERSION,
    }
    return normalized
