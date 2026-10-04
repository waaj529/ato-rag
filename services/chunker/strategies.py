"""Narrative and structured-table source block extraction."""

from dataclasses import dataclass
from typing import Any, Iterator


@dataclass(frozen=True)
class SourceBlock:
    kind: str
    text: str
    heading_path: list[str]
    locator: dict[str, Any]
    row_spans: tuple[tuple[int, int, int], ...] = ()


def _narrative_segments(text: str) -> Iterator[tuple[str, int, int]]:
    offset, segment_start, parts = 0, 0, []
    for line in text.splitlines(keepends=True):
        stripped = line.strip()
        is_table = stripped.startswith("|") and stripped.endswith("|")
        if is_table and parts:
            raw = "".join(parts)
            leading = len(raw) - len(raw.lstrip())
            cleaned = raw.strip()
            if cleaned:
                yield cleaned, segment_start + leading, segment_start + leading + len(cleaned)
            parts = []
        elif not is_table:
            if not parts:
                segment_start = offset
            parts.append(line)
        offset += len(line)
    if parts:
        raw = "".join(parts)
        leading = len(raw) - len(raw.lstrip())
        cleaned = raw.strip()
        if cleaned:
            yield cleaned, segment_start + leading, segment_start + leading + len(cleaned)


def narrative_blocks(document: dict[str, Any]) -> Iterator[SourceBlock]:
    for section in document.get("sections") or []:
        raw_text = str(section.get("text") or "")
        if raw_text.lstrip().startswith("{\\rtf"):
            continue
        path = [str(item) for item in (section.get("heading_path") or []) if item]
        if not path and section.get("heading"):
            path = [str(section["heading"])]
        for text, start, _ in _narrative_segments(raw_text):
            locator = {"section_id": section.get("section_id"), "segment_start": start}
            yield SourceBlock("narrative", text, path, locator)


def _table_rows(table: dict[str, Any]) -> tuple[list[str], list[list[str]]]:
    headers = [str(value).strip() for value in (table.get("headers") or [])]
    rows = [[str(value).strip() for value in row] for row in (table.get("matrix") or [])]
    if rows and headers and rows[0] == headers:
        rows = rows[1:]
    if not headers and rows:
        headers, rows = rows[0], rows[1:]
    return headers, rows


def _project_row(headers: list[str], row: list[str]) -> str:
    cells = []
    for index in range(max(len(headers), len(row))):
        label = headers[index] if index < len(headers) and headers[index] else f"Column {index + 1}"
        value = row[index] if index < len(row) else ""
        cells.append(f"{label}: {value}")
    return " | ".join(cells)


def table_blocks(document: dict[str, Any]) -> Iterator[SourceBlock]:
    for number, table in enumerate(document.get("tables") or []):
        headers, rows = _table_rows(table)
        projected = [_project_row(headers, row) for row in rows]
        if not projected and headers:
            projected = [" | ".join(headers)]
        text, spans, cursor = "", [], 0
        for row_number, row_text in enumerate(projected, start=1):
            if text:
                text += "\n\n"
                cursor += 2
            start = cursor
            text += row_text
            cursor += len(row_text)
            spans.append((row_number, start, cursor))
        if not text:
            continue
        table_id = str(table.get("table_id") or f"table_{number}")
        path = [document.get("title") or "Untitled", f"Table {table_id}"]
        locator = {"section_id": table.get("section_id"), "table_id": table_id,
                   "page_number": table.get("page_number")}
        yield SourceBlock("table", text, path, locator, tuple(spans))

