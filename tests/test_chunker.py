from services.chunker.core import ChunkerConfig, catalog_record, chunk_document, strip_markdown_tables


def fixture_document():
    return {
        "schema_version": "ready-document-1.0",
        "document_id": "doc-1",
        "title": "Test ruling",
        "source_url": "https://example.test/ruling",
        "publisher": "Australian Taxation Office",
        "classification": {
            "corpus": "tax_guidance",
            "source_class": "ato_public_ruling",
            "applicable_periods": ["2025-26"],
        },
        "version": {"version_id": "v1_test", "content_sha256": "abc"},
        "sections": [
            {
                "section_id": "s1",
                "heading": "Ruling",
                "heading_path": ["Ruling", "Application"],
                "text": "Narrative before table.\n\n| A | B |\n| --- | --- |\n| one | two |\n\nNarrative after table.",
                "source_locator": {"char_start": 0, "char_end": 100},
            }
        ],
        "tables": [
            {
                "table_id": "t1",
                "headers": ["A", "B"],
                "matrix": [["A", "B"], ["one", "two"]],
                "page_number": 1,
            }
        ],
        "references": [{"type": "primary_legislation", "reference": "ITAA 1997"}],
    }


def test_markdown_table_removed_but_narrative_kept():
    value = strip_markdown_tables("Before\n\n| A | B |\n| --- | --- |\n| 1 | 2 |\n\nAfter")
    assert "Before" in value and "After" in value
    assert "| A | B |" not in value and "| 1 | 2 |" not in value


def test_narrative_and_table_are_separate_and_deterministic():
    first_parents, first_children = chunk_document(fixture_document())
    second_parents, second_children = chunk_document(fixture_document())
    assert [item["parent_id"] for item in first_parents] == [item["parent_id"] for item in second_parents]
    assert [item["chunk_id"] for item in first_children] == [item["chunk_id"] for item in second_children]
    narrative = [item for item in first_children if item["chunk_type"] == "text"]
    tables = [item for item in first_children if item["chunk_type"] == "table"]
    assert narrative and tables
    assert "one" not in narrative[0]["text"]
    assert "A: one" in tables[0]["text"]
    assert narrative[0]["corpus"] == "tax_guidance"
    assert narrative[0]["source_url"] == fixture_document()["source_url"]
    assert narrative[0]["source_locator"]["section_id"] == "s1"
    assert narrative[0]["parent_chunk_id"] == first_parents[0]["parent_id"]
    assert narrative[0]["source_locator"]["locator_precision"] == "exact"
    assert narrative[0]["source_locator"]["char_start"] == 0
    start = narrative[0]["source_locator"]["char_start"]
    end = narrative[0]["source_locator"]["char_end"]
    assert fixture_document()["sections"][0]["text"][start:end] == narrative[0]["text"]
    assert tables[0]["source_locator"]["locator_precision"] == "table_rows"
    assert tables[0]["source_locator"]["row_start"] == 1


def test_hard_limit_and_lineage():
    document = fixture_document()
    document["sections"][0]["text"] = " ".join(f"word{i}" for i in range(5000))
    config = ChunkerConfig(child_target_tokens=100, child_hard_max_tokens=120, overlap_tokens=10)
    parents, children = chunk_document(document, config)
    assert parents and children
    assert max(item["token_count"] for item in children) <= 120
    parent_ids = {item["parent_id"] for item in parents}
    assert all(item["parent_chunk_id"] in parent_ids for item in children)
    catalog = catalog_record(document)
    assert catalog["source_url"] == document["source_url"]
    assert all(item["version_id"] == document["version"]["version_id"] for item in children)


def test_document_id_namespaces_source_local_version_ids():
    first = fixture_document()
    second = fixture_document()
    second["document_id"] = "doc-2"
    first_parents, first_children = chunk_document(first)
    second_parents, second_children = chunk_document(second)
    assert first_parents[0]["parent_id"] != second_parents[0]["parent_id"]
    assert first_children[0]["chunk_id"] != second_children[0]["chunk_id"]
