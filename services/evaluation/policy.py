"""Fail-closed scope and contamination policy for benchmark candidates."""

import re


BLOCKED_TEXT = (
    "browse all legislation", "public rulings practical compliance guidelines",
    "this cover sheet is provided for information only", "does not form part of",
    "on this page", "skip to", "last updated", "subscribe to", "copyright",
    "privacy", "accessibility", "print this page", "ato law navigation",
    "pdf version is the authorised", "pdf version is the authorized",
    "authorised consolidated version", "authorized consolidated version",
    "ato references", "issn:", "finalisation of this draft", "adobe reader",
    "pdf viewer may not be able", "publications distribution service", "1300 720 092",
    "if you rely on this ruling", "a public ruling is an expression of the commissioner",
    "this publication provides you with the following level of protection",
    "we acknowledge the traditional owners", "page not found | australian taxation office",
    "omit ‘", "omit '", "correctly rely on it", "part ivaaa", "relying on this ruling",
    "relying on this determination", "legally binding", "good faith, the commissioner will",
    "good faith, we will apply", "is a public ruling for the purposes of",
    "is a 'public ruling' for the purposes of",
)
BLOCKED_LABELS = (
    "on this page", "contact details", "federal court", "request for valuation",
    "notice of withdrawal", "contents", "how to obtain this publication",
    "in footnote", "omit ‘", "omit '", "adobe reader",
    "page not found", "what this ruling is about",
    "by phone", "privacy notice", "school education", "interpretation now",
    "things to know", "you need to know", "what you need to answer this question",
    "completing this section", "key benchmark range", "about the tax help program",
    "review permissions in access manager",
)
TAX_ACTS = (
    "income tax assessment act 1997", "income tax assessment act 1936",
    "taxation administration act 1953", "fringe benefits tax assessment act 1986",
    "a new tax system (goods and services tax) act 1999",
    "superannuation industry (supervision) act 1993",
    "income tax (transitional provisions) act 1997",
)
TAX_REGULATIONS = (
    "income tax assessment", "taxation administration", "fringe benefits tax",
    "a new tax system (goods and services tax)", "superannuation industry (supervision)",
)
FORM_HEADING = re.compile(
    r"^(?:[A-Z]?\d+[A-Z]?\s+(?:subtotal|total|item|label)|step\s+\d+|table\s+\d+)", re.I)
MATRIX = re.compile(r"(?:\d+(?:\.\d+)?%\s*){4,}")
DOT_LEADERS = re.compile(r"\.{4,}")


def label_is_clean(document: dict, section: dict) -> bool:
    title = str(document.get("title") or "")
    path = section.get("heading_path") or [section.get("heading") or ""]
    heading = " ".join(path)
    leaf = str(path[-1]) if path else ""
    combined = f"{title} {heading}".casefold()
    if len(title) > 260 or len(heading) > 220:
        return False
    if any(value in combined for value in BLOCKED_LABELS):
        return False
    generic = {"introduction", "about this guide", "summary", "addendum", "preamble",
               "ruling", "overview", "guidance notes", "things to know", "you need to know",
               "what's new"}
    if leaf.strip(" -?").casefold() in generic:
        return False
    ref = str(document.get("canonical_reference_id") or "").strip().casefold()
    clean_leaf = re.sub(r"^(?:taxation\s+ruling|taxation\s+determination|miscellaneous\s+taxation\s+ruling|class\s+ruling|product\s+ruling)\s+", "", leaf.strip(), flags=re.I).casefold()
    if ref and clean_leaf == ref:
        return False
    definition = re.search(r"\bdefinition:\s*(.*)", leaf.strip(), re.I)
    if definition and not re.match(r"[A-Za-z]", definition.group(1)):
        return False
    if any(value in combined for value in (" statistics", "episode ", "key messages")):
        return False
    if re.fullmatch(r"question\s+\d+", leaf.strip(), re.I):
        return False
    if FORM_HEADING.match(leaf.strip()) or MATRIX.search(combined) or DOT_LEADERS.search(combined):
        return False
    return not bool(re.search(r"\b[0-9a-f]{8}(?:[-_ ][0-9a-f]{4}){3}", combined, re.I))


def legislation_is_in_scope(document: dict) -> bool:
    classification = document.get("classification") or {}
    source_class = classification.get("source_class")
    if source_class not in {"commonwealth_statute", "commonwealth_regulation"}:
        return True
    title = str(document.get("title") or "").casefold()
    allowed = TAX_ACTS if source_class == "commonwealth_statute" else TAX_REGULATIONS
    return any(value in title for value in allowed)
