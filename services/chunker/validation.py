"""Canonical-source validation for child chunk locators."""

from collections import OrderedDict
from collections.abc import Iterable
import gzip
import json
from pathlib import Path

from .strategies import _project_row, _table_rows
from services.source_registry import normalize_document


class SourceResolver:
    def __init__(self, import_manifests: Path | Iterable[Path], cache_size: int = 128):
        paths = (import_manifests,) if isinstance(import_manifests, Path) else tuple(import_manifests)
        self.paths: dict[str, tuple[Path, str]] = {}
        for import_manifest in paths:
            manifest = json.loads(import_manifest.read_text())
            source_root = Path(manifest["source_root"])
            with gzip.open(manifest["inventory_path"], "rt", encoding="utf-8") as handle:
                for line in handle:
                    entry = json.loads(line)
                    document_id = entry["document_id"]
                    location = (source_root, entry["relative_path"])
                    if document_id in self.paths and self.paths[document_id] != location:
                        raise ValueError(f"duplicate document ID across corpora: {document_id}")
                    self.paths[document_id] = location
        self.cache: OrderedDict[str, dict] = OrderedDict()
        self.cache_size = cache_size

    def __contains__(self, document_id: object) -> bool:
        return isinstance(document_id, str) and document_id in self.paths

    def has_document(self, document_id: object) -> bool:
        return self.__contains__(document_id)

    def document(self, document_id: str) -> dict:
        if document_id in self.cache:
            self.cache.move_to_end(document_id)
            return self.cache[document_id]
        if not self.has_document(document_id):
            raise KeyError(f"Unknown document ID: {document_id}")
        source_root, relative_path = self.paths[document_id]
        document = normalize_document(json.loads((source_root / relative_path).read_text()))
        self.cache[document_id] = document
        if len(self.cache) > self.cache_size:
            self.cache.popitem(last=False)
        return document


def _validate_text(record: dict, document: dict) -> str | None:
    locator = record.get("source_locator")
    if locator is None:
        return "missing_source_locator"
    if not isinstance(locator, dict):
        return "invalid_source_locator"
    section = next((item for item in document.get("sections", [])
                    if item.get("section_id") == locator.get("section_id")), None)
    if section is None:
        return "missing_source_section"
    section_text = section.get("text", "")
    start, end = locator.get("char_start"), locator.get("char_end")
    if (
        not isinstance(start, int)
        or not isinstance(end, int)
        or not 0 <= start <= end <= len(section_text)
    ):
        return "invalid_character_span"
    if section_text[start:end] != record.get("text"):
        return "inexact_character_span"
    if locator.get("locator_precision") != "exact":
        return "invalid_text_locator_precision"
    return None


def _projected_rows(table: dict) -> tuple[str, list[tuple[int, int, int]]]:
    """Rebuild the table block text and row spans exactly as ``table_blocks`` does."""
    headers, rows = _table_rows(table)
    projected = [_project_row(headers, row) for row in rows]
    if not projected and headers:
        projected = [" | ".join(headers)]
    text, spans, cursor = "", [], 0
    for number, row_text in enumerate(projected, start=1):
        if text:
            text += "\n\n"
            cursor += 2
        start = cursor
        text += row_text
        cursor += len(row_text)
        spans.append((number, start, cursor))
    return text, spans


def _validate_table(record: dict, document: dict) -> str | None:
    locator = record.get("source_locator")
    if locator is None:
        return "missing_source_locator"
    if not isinstance(locator, dict):
        return "invalid_source_locator"
    table = next((item for item in document.get("tables", [])
                  if str(item.get("table_id")) == str(locator.get("table_id"))), None)
    if table is None:
        return "missing_source_table"
    text, spans = _projected_rows(table)
    if not spans:
        return "empty_source_table"
    start, end = locator.get("row_start"), locator.get("row_end")
    if not isinstance(start, int) or not isinstance(end, int) or not 1 <= start <= end <= len(spans):
        return "invalid_table_row_range"
    if locator.get("locator_precision") != "table_rows":
        return "invalid_table_locator_precision"
    claimed = text[spans[start - 1][1]:spans[end - 1][2]]
    if record.get("text") not in claimed:
        return "inexact_table_rows"
    return None


def validate_source_locator(record: dict, resolver: SourceResolver) -> str | None:
    locator = record.get("source_locator")
    if locator is None:
        return "missing_source_locator"
    if not isinstance(locator, dict):
        return "invalid_source_locator"
    document_id = record.get("document_id")
    if not resolver.has_document(document_id):
        return "unknown_document_id"
    document = resolver.document(document_id)
    if record.get("chunk_type") == "text":
        return _validate_text(record, document)
    if record.get("chunk_type") == "table":
        return _validate_table(record, document)
    return "unknown_chunk_type"
