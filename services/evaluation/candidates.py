"""Conservative Phase 0 candidate selection from canonical source passages."""

import re

from .policy import BLOCKED_TEXT, label_is_clean, legislation_is_in_scope
from .questions import realistic_question

YEAR = re.compile(r"\b(?:19|20)\d{2}(?:[–-]\d{2})?\b")
RULING_PREFIXES = {
    "practical_compliance_guideline": ("pcg ",), "taxation_determination": ("td ",),
    "public_ruling": ("tr ", "cr ", "pr ", "gstr ", "mt "), "law_companion_ruling": ("lcr ",),
}


def source_class_is_consistent(document: dict) -> bool:
    classification = document.get("classification") or {}
    source_class = classification.get("source_class")
    title = str(document.get("title") or "").casefold()
    reference = str(document.get("canonical_reference_id") or "").casefold()
    document_type = str(classification.get("document_type") or "").casefold()
    if classification.get("page_status") in {"draft", "withdrawn"}:
        return False
    if source_class == "court_decision":
        return bool(re.search(r"\[\d{4}\]\s+[A-Z]{2,}\s+\d+",
                              title + " " + reference, re.I))
    if source_class in RULING_PREFIXES:
        return reference.startswith(RULING_PREFIXES[source_class])
    if source_class in {"commonwealth_statute", "commonwealth_regulation"}:
        return (bool(document.get("statute_version"))
                and "legislation.gov.au" in str(document.get("source_url"))
                and legislation_is_in_scope(document))
    if source_class == "ato_public_guidance":
        ruling_prefixes = tuple(prefix for values in RULING_PREFIXES.values() for prefix in values)
        return not reference.startswith(ruling_prefixes)
    return False


def passage_is_substantive(document: dict, section: dict, passage: str) -> bool:
    value = passage.casefold()
    if any(item in value for item in BLOCKED_TEXT):
        return False
    if not label_is_clean(document, section):
        return False
    words = re.findall(r"[a-z]{3,}", value)
    if len(words) < 28 or len(set(words)) < 16:
        return False
    if not passage.rstrip().endswith((".", "!", "?")):
        return False
    if not re.match(r"^[A-Z0-9(\-•]", passage.lstrip()):
        return False
    norm_passage = " ".join(re.findall(r"\w+", value))
    doc_title = " ".join(re.findall(r"\w+", str(document.get("title") or "").casefold()))
    sec_title = " ".join(re.findall(r"\w+", str(section.get("heading") or "").casefold()))
    if norm_passage in {doc_title, sec_title}:
        return False
    question_norm = " ".join(re.findall(r"\w+", realistic_question(document, section, passage).casefold()))
    if norm_passage in question_norm or re.search(r"^\s*1\s+[A-Za-z].*\b2\s+[A-Za-z]", passage):
        return False
    return not value.startswith(("this document", "this page", "the following table",
                                 "in footnote", "omit ", "insert ", "after paragraph"))


def passage_dedupe_key(passage: str) -> str:
    return " ".join(re.findall(r"[a-z]{3,}", passage.casefold()))


def _operative_period(document: dict) -> str | None:
    periods = (document.get("classification") or {}).get("applicable_periods") or []
    annual = sorted(str(value) for value in periods
                    if re.fullmatch(r"\d{4}[-–]\d{2}", str(value)))
    if not annual:
        return None
    if (document.get("classification") or {}).get("historical_guidance"):
        return annual[-1]
    issued = _issue_year(document)
    if issued is not None and int(annual[-1][:4]) + 1 < issued:
        return None
    return annual[-1]


def _issue_year(document: dict) -> int | None:
    years = [int(m.group(1)) for key in ("issue_date", "issued", "published", "decision_date")
             if (m := re.search(r"\b((?:19|20)\d{2})\b", str((document.get("dates") or {}).get(key) or "")))]
    ref = str(document.get("canonical_reference_id") or "")
    if (m := re.search(r"\b((?:19|20)\d{2}|\d{2})/", ref)):
        years.append(int(m.group(1)) if len(m.group(1)) == 4 else 1900 + int(m.group(1)))
    return max(years) if years else None


def temporal_is_consistent(document: dict, passage: str) -> bool:
    annual = _operative_period(document)
    if not annual:
        return True
    start = int(annual[:4])
    return not any(int(value[:4]) > start + 1 for value in YEAR.findall(passage))


def applicable_as_of(document: dict) -> str | None:
    annual = _operative_period(document)
    return f"{int(annual[:4]) + 1}-06-30" if annual else None


def extract_substantive_passage(document: dict) -> tuple | None:
    if not source_class_is_consistent(document):
        return None
    for section in document.get("sections") or []:
        text, cursor = str(section.get("text") or ""), 0
        for paragraph in text.split("\n\n"):
            start = cursor + len(paragraph) - len(paragraph.lstrip())
            cursor += len(paragraph) + 2
            clean = paragraph.strip()
            if len(clean) < 120 or "|" in clean:
                continue
            bounded = _bounded_passage(clean)
            if bounded is None:
                continue
            passage, relative_start = bounded
            if passage_is_substantive(document, section, passage) and temporal_is_consistent(document, passage):
                passage_start = start + relative_start
                return section, passage, passage_start, passage_start + len(passage)
    return None


def _bounded_passage(clean: str) -> tuple[str, int] | None:
    method = clean.casefold().find("method statement")
    if method >= 0:
        starts = list(re.finditer(r"(?:^|\n)\(\d+\)", clean[:method]))
        start = starts[-1].start() + (1 if starts[-1].group().startswith("\n") else 0) if starts else 0
        following = re.search(r"\n\(\d+\)", clean[method + 1:])
        end = method + 1 + following.start() if following else len(clean)
        passage = clean[start:end].strip()
        steps = {int(value) for value in re.findall(r"\bStep\s+(\d+)\.", passage, re.I)}
        if len(steps) < 2 or not passage.endswith((".", "!", "?")):
            return None
        return passage, clean.index(passage, start)
    limit = min(len(clean), 650)
    endings = [match.end() for match in re.finditer(r"[.!?](?=\s|$)", clean[:limit])]
    end = endings[-1] if endings and endings[-1] >= 120 else 0
    return (clean[:end].strip(), 0) if end else None
