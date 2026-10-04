"""Deterministic legal-identifier normalization, extraction and publication."""

import re

import psycopg


ATO_PREFIXES = (
    "SMSFR", "SMSFD", "GSTR", "GSTD", "PSLA", "LCR", "PCG", "SGR",
    "FTD", "SGD", "TR", "TD", "IT", "CR", "PR", "MT", "PS", "TA",
    "ER", "ST",
)
_ATO = "|".join(ATO_PREFIXES)
PATTERNS = (
    re.compile(rf"\b(?:{_ATO})\s+\d{{2,4}}/\d+[A-Z0-9]*\b", re.I),
    re.compile(r"\[\d{4}\]\s+(?:HCA|FCAFC|FCA)\s+\d+", re.I),
    re.compile(r"\bC\d{4}C\d+#\d+[A-Z]?(?:-\d+[A-Z]?)?\b", re.I),
    re.compile(r"\b(?:s|section)\s+(\d+[A-Z]?(?:[-.]\d+[A-Z]?)*(?:\(\d+[A-Z]?\))*)", re.I),
    re.compile(r"\b(?:Income Tax Assessment Act|Income Tax Assessment Regulations|"
               r"Taxation Administration Act)\s+\d{4}\b", re.I),
    re.compile(r"\[(\d{1,3})\]"),
)
GENERIC_TERMS = frozenset({
    "what", "which", "when", "how", "does", "did", "is", "are", "the", "this", "that",
    "about", "under", "into", "from", "with", "for", "provide", "provides", "apply", "applies",
    "guidance", "rule", "establish", "conclude", "issue", "address", "information",
    "required", "requirements", "determine", "commissioner", "high", "court", "ato",
    "treated", "purposes",
})


def normalize_identifier(value: str) -> str:
    return "".join(character for character in value.casefold() if character.isalnum())


def extract_identifiers(query: str) -> tuple[str, ...]:
    identifiers: list[str] = []
    for index, pattern in enumerate(PATTERNS):
        for match in pattern.finditer(query):
            value = match.group(1) if match.lastindex else match.group(0)
            if pattern is PATTERNS[-1]:
                value = f"para_{value}"
            normalized = normalize_identifier(value)
            if normalized and normalized not in identifiers:
                identifiers.append(normalized)
    return tuple(identifiers)


def lexical_terms(query: str) -> str:
    value = query
    for pattern in PATTERNS:
        value = pattern.sub(" ", value)
    words = re.findall(r"[A-Za-z0-9]+(?:[-.][A-Za-z0-9]+)*", value.casefold())
    retained = [word for word in words if len(word) > 1 and word not in GENERIC_TERMS]
    return " ".join(retained) or query


def prefers_court_opening(identifiers: tuple[str, ...]) -> bool:
    has_court_citation = any(re.fullmatch(r"\d{4}(?:hca|fcafc|fca)\d+", value)
                             for value in identifiers)
    has_pinpoint = any(value.startswith("para") for value in identifiers)
    return has_court_citation and not has_pinpoint


def populate_exact_identifiers(connection: psycopg.Connection) -> dict[str, int]:
    """Atomically replace identifier rows from the published retrieval chunks."""
    statements = {
        "document_id": "document_id",
        "document_title": "substring(contextual_header from '\\[DOCUMENT: ([^]]+)\\]')",
        "citation": "canonical_reference_id",
        "section": "source_locator->>'section_id'",
    }
    counts: dict[str, int] = {}
    with connection.transaction():
        connection.execute("TRUNCATE exact_identifiers")
        for identifier_type, expression in statements.items():
            result = connection.execute(
                f"""INSERT INTO exact_identifiers
                    (normalized_identifier, identifier_type, chunk_id)
                    SELECT lower(regexp_replace({expression}, '[^[:alnum:]]', '', 'g')),
                           %s, chunk_id
                    FROM retrieval_chunks
                    WHERE is_active AND nullif({expression}, '') IS NOT NULL
                    ON CONFLICT DO NOTHING""",
                (identifier_type,),
            )
            counts[identifier_type] = result.rowcount
        result = connection.execute(
            """INSERT INTO exact_identifiers
                (normalized_identifier, identifier_type, chunk_id)
                SELECT lower(regexp_replace(split_part(source_locator->>'section_id', '#', 2),
                       '[^[:alnum:]]', '', 'g')), 'section', chunk_id
                FROM retrieval_chunks
                WHERE is_active AND source_locator->>'section_id' LIKE '%#%'
                ON CONFLICT DO NOTHING"""
        )
        counts["section_alias"] = result.rowcount
    return counts
