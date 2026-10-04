"""Tests for child chunk locator and source validation."""

from unittest.mock import MagicMock
from services.chunker.validation import (
    SourceResolver, _validate_table, _validate_text, validate_source_locator,
)


def test_character_span_exceeding_section_text_is_rejected():
    document = {"sections": [{"section_id": "s1", "text": "Hello world"}]}
    valid_record = {
        "text": "Hello",
        "source_locator": {"section_id": "s1", "char_start": 0, "char_end": 5, "locator_precision": "exact"},
    }
    assert _validate_text(valid_record, document) is None

    exceeding_record = {
        "text": "world",
        "source_locator": {"section_id": "s1", "char_start": 6, "char_end": 999, "locator_precision": "exact"},
    }
    assert _validate_text(exceeding_record, document) == "invalid_character_span"


def test_validate_source_locator_rejects_invalid_metadata():
    resolver = MagicMock(spec=SourceResolver)
    resolver.has_document.side_effect = lambda doc_id: doc_id == "doc-known"
    resolver.document.return_value = {"sections": [{"section_id": "s1", "text": "Hello world"}]}

    # Missing locator
    assert validate_source_locator({}, resolver) == "missing_source_locator"
    assert validate_source_locator({"source_locator": None}, resolver) == "missing_source_locator"

    # Non-object locator
    assert validate_source_locator({"source_locator": "not-a-dict"}, resolver) == "invalid_source_locator"
    assert validate_source_locator({"source_locator": [1, 2, 3]}, resolver) == "invalid_source_locator"

    # Unknown or missing document ID
    valid_loc = {"section_id": "s1", "char_start": 0, "char_end": 5, "locator_precision": "exact"}
    assert validate_source_locator({"source_locator": valid_loc}, resolver) == "unknown_document_id"
    assert validate_source_locator({"document_id": "unknown-doc", "source_locator": valid_loc}, resolver) == "unknown_document_id"

    # Valid resolution
    assert validate_source_locator(
        {"document_id": "doc-known", "chunk_type": "text", "text": "Hello", "source_locator": valid_loc},
        resolver,
    ) is None


def table_record(text, **locator_overrides):
    locator = {"table_id": "t1", "row_start": 1, "row_end": 1,
               "locator_precision": "table_rows"}
    locator.update(locator_overrides)
    return {"document_id": "d", "chunk_type": "table", "text": text, "source_locator": locator}


def test_table_locator_rejects_text_that_does_not_match_its_claimed_rows():
    document = {"tables": [{"table_id": "t1", "headers": ["A", "B"],
                            "matrix": [["A", "B"], ["one", "two"]]}]}
    assert _validate_table(table_record("A: one | B: two"), document) is None
    assert _validate_table(table_record("A: nine | B: ten"), document) == "inexact_table_rows"


def test_table_locator_rejects_a_row_range_the_generator_cannot_emit():
    document = {"tables": [{"table_id": "t1", "headers": ["A", "B"],
                            "matrix": [["A", "B"], ["one", "two"]]}]}
    assert _validate_table(table_record("A: one | B: two", row_start=2), document) == (
        "invalid_table_row_range")


def test_header_only_table_projects_the_same_row_the_generator_emits():
    document = {"tables": [{"table_id": "t1", "headers": ["A", "B"], "matrix": []}]}
    assert _validate_table(table_record("A | B"), document) is None


def test_table_locator_rejects_a_missing_table_or_wrong_precision():
    document = {"tables": [{"table_id": "t1", "headers": ["A"], "matrix": [["one"]]}]}
    assert _validate_table(table_record("A: one", table_id="missing"), document) == (
        "missing_source_table")
    assert _validate_table(table_record("A: one", locator_precision="exact"), document) == (
        "invalid_table_locator_precision")
