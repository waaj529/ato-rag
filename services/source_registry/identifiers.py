"""Evidence-exact canonical citation derivation for imported source documents.

URL evidence drives repairs. A title can choose an official short pre-2000 form only
when the URL independently corroborates the same prefix, year and ruling number.
Contradicted citations are dropped; citations without evidence are retained unchanged.
"""

import re
from dataclasses import dataclass
from urllib.parse import unquote

from .authority import normalize_authority
from .sections import normalize_section_ids

RULE_VERSION = "citation-evidence-v3"

# Longest first: PSLA before PS, SMSFR/SMSFD before SGD, GSTR before GSTD.
PREFIXES = ("SMSFR", "SMSFD", "GSTR", "GSTD", "PSLA", "LCR", "PCG", "SGR", "FTD",
            "SGD", "TR", "TD", "IT", "CR", "PR", "MT", "PS", "TA", "ER", "ST")
_PREFIXES = "|".join(PREFIXES)

SCOPE = re.compile(rf"^(?:{_PREFIXES}) ")
FILENAME_CITATION = re.compile(r"^([A-Za-z]+)(\d{4})-(\d+)")
DOCID_CITATION = re.compile(r"(?:docid=|/)(?:[A-Z]+/)?([A-Za-z]+)(\d{3,})(?:/|&|$)", re.I)
TITLE_CITATION = re.compile(rf"\b({_PREFIXES})\s+(\d{{2}}|\d{{4}})/(\d+)\b", re.I)


@dataclass(frozen=True)
class Citation:
    original: str | None
    value: str | None
    resolution: str
    evidence: str | None
    rule_version: str = RULE_VERSION


def _basename(source_url: object) -> str:
    value = unquote(str(source_url or ""))
    if "filename=" in value:
        value = value.split("filename=", 1)[1].split("&", 1)[0]
    value = value.split("?", 1)[0].split("#", 1)[0]
    return value.rstrip("/").rsplit("/", 1)[-1]


def _from_source_url(source_url: object) -> str | None:
    name = _basename(source_url)
    if name.lower().endswith(".pdf"):
        name = name[:-4]
    match = FILENAME_CITATION.match(name)
    if match and match.group(1).upper() in PREFIXES:
        prefix, year, number = match.groups()
        return f"{prefix.upper()} {year}/{int(number)}"
    docid = DOCID_CITATION.search(unquote(str(source_url or "")))
    if not docid or docid.group(1).upper() not in {"MT", "TD"}:
        return None
    prefix, digits = docid.groups()
    year_length = 4 if digits.startswith(("19", "20")) else 2
    year, number = digits[:year_length], digits[year_length:]
    if not number:
        return None
    return f"{prefix.upper()} {year}/{int(number)}"


def _title_equivalent(title: object, derived: str) -> str | None:
    prefix, remainder = derived.split(" ", 1)
    year, number = remainder.split("/", 1)
    for match in TITLE_CITATION.finditer(str(title or "")):
        found_prefix, found_year, found_number = match.groups()
        year_matches = found_year == year or (int(year) < 2000 and year.endswith(found_year))
        if found_prefix.upper() == prefix and year_matches and int(found_number) == int(number):
            return f"{found_prefix.upper()} {found_year}/{int(found_number)}"
    return None


def _reconcile(original: str, derived: str) -> tuple[str, str | None, str | None]:
    """Compare a stored citation against URL-derived evidence."""
    stored_prefix, _, stored_rest = original.partition(" ")
    stored_year, _, stored_number = stored_rest.partition("/")
    derived_prefix, derived_rest = derived.split(" ", 1)
    derived_year, _, derived_number = derived_rest.partition("/")
    if stored_prefix != derived_prefix:
        return "flagged", None, "prefix mismatch"
    years_match = stored_year == derived_year or (
        (len(stored_year) == 2 and derived_year.endswith(stored_year)) or
        (len(derived_year) == 2 and stored_year.endswith(derived_year))
    )
    if years_match:
        if stored_number.startswith(derived_number):
            return "confirmed", original, "source_url"
        return "flagged", None, "number mismatch"
    if len(stored_year) == 2 and derived_year.startswith(stored_year):
        return "normalized", derived, "source_url"
    return "flagged", None, "year mismatch"


def resolve_citation(document: dict) -> Citation:
    """Classify a citation as confirmed, normalized, uncorroborated, flagged or out of scope."""
    prior = document.get("canonical_reference") or {}
    stored = prior.get("original") or document.get("canonical_reference_id")
    original = str(stored) if stored else None
    if original is None or not SCOPE.match(original):
        return Citation(original, original, "not_evaluated", None)

    derived = _from_source_url(document.get("source_url"))
    if derived is None:
        if original in str(document.get("title") or ""):
            return Citation(original, original, "confirmed", "title")
        return Citation(original, original, "uncorroborated", None)
    titled = _title_equivalent(document.get("title"), derived)
    if titled and titled != derived:
        resolution = "confirmed" if titled == original else "normalized"
        return Citation(original, titled, resolution, "title+source_url")
    resolution, value, evidence = _reconcile(original, derived)
    return Citation(original, value, resolution, evidence)


def normalize_document(document: dict) -> dict:
    """Return a copy with derived section ids and a resolved canonical citation."""
    normalized = normalize_authority(normalize_section_ids(document))
    prior = normalized.get("canonical_reference") or {}
    if prior.get("rule_version") == RULE_VERSION:
        return normalized
    if prior.get("rule_version"):
        derived = _from_source_url(normalized.get("source_url"))
        titled = _title_equivalent(normalized.get("title"), derived) if derived else None
        current = normalized.get("canonical_reference_id")
        title_up = titled is not None and titled != current
        docid_up = (derived is not None and derived.startswith(("MT ", "TD "))
                    and (derived != current or prior.get("evidence") != "source_url"))
        if not title_up and not docid_up:
            return normalized
    citation = resolve_citation(normalized)
    normalized = dict(normalized)
    normalized["canonical_reference_id"] = citation.value
    normalized["canonical_reference"] = {
        "original": citation.original, "resolution": citation.resolution,
        "evidence": citation.evidence, "rule_version": citation.rule_version,
    }
    return normalized
