"""Deterministic legislation section identity derived from imported evidence.

A legislation document's own ``document_id`` encodes its register and section
(``leg-c2026c00280-1-1-350c2f64``); the ``source_url`` fragment names the same section
independently. A section id is derived only when the two agree, and the register is
cross-checked against ``statute_version.register_id``.

Two upstream quirks are handled explicitly, both observed across the full corpus:

* Definition documents encode ``995-1-def-wine-tax-credit`` and the fragment carries
  only the slug ``wine-tax-credit``.
* ``document_id`` truncates long slugs (``…-def-very-large-superannuation-balan``)
  while the fragment holds the complete one
  (``very-large-superannuation-balance-earnings-component``), so the fragment is
  preferred whenever it extends the recorded slug.
"""

import re

RULE_VERSION = "legislation-section-v1"

DEFINITION = re.compile(r"^(.+?)-def-(.+)$")


def _document_id_parts(document_id: str) -> tuple[str, str] | None:
    """Return ``(register, section expression)`` for a legislation document id."""
    if not document_id.startswith("leg-"):
        return None
    parts = document_id[len("leg-"):].split("-")
    if len(parts) < 3:
        return None
    section = "-".join(parts[1:-1])
    return (parts[0], section) if section else None


def _url_fragment(source_url: object) -> str:
    return str(source_url or "").partition("#")[2]


def _render(section: str, fragment: str) -> tuple[str, str | None] | None:
    """Return ``(rendered section, definition slug)`` corroborated by the fragment."""
    expression, value = section.casefold(), fragment.casefold()
    if expression == value:
        return fragment, None
    match = DEFINITION.match(expression)
    if match:
        head, slug = match.group(1), match.group(2)
        if value == slug:
            return section, slug
        if value.startswith(slug):
            return f"{head}-def-{value}", value
        return None
    if expression.endswith("-" + value):
        return section, None
    return None


def legislation_section_id(document: dict) -> dict | None:
    """Derive a stable ``REGISTER#section`` id, or ``None`` for non-legislation."""
    document_id = str(document.get("document_id") or "")
    parts = _document_id_parts(document_id)
    if parts is None:
        return None
    identifier_register, section = parts
    declared = str((document.get("statute_version") or {}).get("register_id") or "")
    if declared and declared.upper() != identifier_register.upper():
        return None
    fragment = _url_fragment(document.get("source_url"))
    if not fragment:
        return None
    rendered = _render(section, fragment)
    if rendered is None:
        return None
    register = (declared or identifier_register).upper()
    return {
        "value": f"{register}#{rendered[0]}",
        "register_id": register,
        "section": rendered[0],
        "definition": rendered[1],
        "rule_version": RULE_VERSION,
    }


def normalize_section_ids(document: dict) -> dict:
    """Return a copy of the document with derived legislation section ids applied."""
    derived = legislation_section_id(document)
    sections = document.get("sections") or []
    if derived is None or not sections:
        return document
    rewritten = []
    for section in sections:
        current = section.get("section_id")
        if current == derived["value"]:
            rewritten.append(section)
            continue
        updated = dict(section)
        updated["source_section_id"] = current
        updated["section_id"] = derived["value"]
        rewritten.append(updated)
    if all(original is updated for original, updated in zip(sections, rewritten)):
        return document
    normalized = dict(document)
    normalized["sections"] = rewritten
    normalized["section_id_resolution"] = derived
    return normalized
