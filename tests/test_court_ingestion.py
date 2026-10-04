"""Contract tests for the isolated official-court ingestion adapter."""

import hashlib
from io import BytesIO
import json
from zipfile import ZipFile

import pytest

from services.court_ingestion import pipeline
from services.court_ingestion.fetcher import CourtSource, FetchedSource, validate_source
from services.court_ingestion.parser import parse_judgment
from services.court_ingestion.records import ready_document
from services.source_registry.ready_import import import_corpus


HTML = b"""<!doctype html><html><head><title>Commissioner of Taxation v Example
[2024] FCA 123</title></head><body><main>
<h1>Commissioner of Taxation v Example [2024] FCA 123</h1>
<p>Judgment delivered 12 March 2024</p><p>SMITH J</p>
<p>[1] This appeal concerns the proper construction of an income tax provision.</p>
<p>[2] The taxpayer derived assessable income in the relevant income year.</p>
</main></body></html>"""
SOURCE = CourtSource(
    "https://www.judgments.fedcourt.gov.au/judgments/example",
    "Federal Court of Australia", "[2024] FCA 123",
)


def fetched() -> FetchedSource:
    return FetchedSource(SOURCE, HTML, "text/html", hashlib.sha256(HTML).hexdigest())


def test_only_explicit_official_https_sources_are_allowed():
    validate_source(SOURCE)
    with pytest.raises(ValueError, match="allowlisted"):
        validate_source(CourtSource("https://example.com/case", "Example", "[2024] FCA 1"))


def test_parser_requires_citation_evidence_and_preserves_numbered_paragraphs():
    parsed = parse_judgment(HTML, "[2024] FCA 123")
    assert [number for number, _ in parsed.paragraphs] == [1, 2]
    assert parsed.decision_date == "12 March 2024"
    assert parsed.judges == ("SMITH J",)
    with pytest.raises(ValueError, match="corroborate"):
        parse_judgment(HTML, "[2024] FCA 999")


def test_docx_judgment_preserves_numbered_paragraphs():
    xml = """<w:document xmlns:w="x"><w:body>
    <w:p><w:r><w:t>Example v Commissioner [2022] HCA 34</w:t></w:r></w:p>
    <w:p><w:r><w:t>[1] The first substantive judgment paragraph has enough words.</w:t></w:r></w:p>
    <w:p><w:r><w:t>[2] The second substantive judgment paragraph also has enough words.</w:t></w:r></w:p>
    </w:body></w:document>"""
    data = BytesIO()
    with ZipFile(data, "w") as archive:
        archive.writestr("word/document.xml", xml)
    parsed = parse_judgment(data.getvalue(), "[2022] HCA 34",
                            "application/vnd.openxmlformats-officedocument.wordprocessingml.document")
    assert [number for number, _ in parsed.paragraphs] == [1, 2]


def test_pdf_layout_can_place_case_name_before_a_late_citation(monkeypatch):
    blocks = ["HIGH COURT OF AUSTRALIA", *[f"Matter {value}" for value in range(32)],
              "Commissioner of Taxation v Example", "[2025] HCA 30",
              "[1] This substantive judgment paragraph contains enough words to be retained."]
    monkeypatch.setattr("services.court_ingestion.parser._document_blocks",
                        lambda body, content_type: (blocks[0], blocks))
    parsed = parse_judgment(b"pdf", "[2025] HCA 30", "application/pdf")
    assert parsed.title == "Commissioner of Taxation v Example [2025] HCA 30"
    assert parsed.paragraphs[0][0] == 1


def test_ready_document_carries_case_metadata_and_exact_pinpoints():
    record = ready_document(fetched(), parse_judgment(HTML, SOURCE.neutral_citation))
    assert record["schema_version"] == "ready-document-1.0"
    assert record["classification"]["source_class"] == "court_decision"
    assert record["case_metadata"]["neutral_citation"] == "[2024] FCA 123"
    assert record["sections"][0]["source_locator"] == {
        "paragraph_start": 1, "paragraph_end": 1,
    }


def test_atomic_output_is_accepted_by_existing_importer(tmp_path, monkeypatch):
    seeds = tmp_path / "seeds.json"
    seeds.write_text(json.dumps([{
        "source_url": SOURCE.source_url, "court": SOURCE.court,
        "neutral_citation": SOURCE.neutral_citation,
    }]))
    monkeypatch.setattr(pipeline, "fetch_source", lambda source, timeout: fetched())
    corpus = tmp_path / "court_ready"
    assert pipeline.build_corpus(seeds, corpus)["valid_for_chunking"] is True
    assert (corpus / f"raw/{fetched().raw_sha256}.html").read_bytes() == HTML
    manifest = import_corpus(corpus, {
        "corpus_id": "court_ready", "required_schema": "ready-document-1.0",
        "required_verification_flag": "valid_for_chunking",
    }, tmp_path / "inventory.jsonl.gz")
    assert manifest["actual"]["unique_documents"] == 1
    with pytest.raises(ValueError, match="refusing to replace"):
        pipeline.build_corpus(seeds, corpus)


def test_batch_skips_one_blocked_seed_and_publishes_successes(tmp_path, monkeypatch):
    blocked = {"source_url": "https://www.hcourt.gov.au/blocked",
               "court": "High Court of Australia", "neutral_citation": "[2024] HCA 9"}
    good = {"source_url": SOURCE.source_url, "court": SOURCE.court,
            "neutral_citation": SOURCE.neutral_citation}
    seeds = tmp_path / "seeds.json"
    seeds.write_text(json.dumps([blocked, good]))

    def fetch(source, timeout):
        if source.neutral_citation == blocked["neutral_citation"]:
            raise ValueError("security challenge")
        return fetched()

    monkeypatch.setattr(pipeline, "fetch_source", fetch)
    report = pipeline.build_corpus(seeds, tmp_path / "partial")
    assert (report["attempted"], report["document_count"], report["skipped"]) == (2, 1, 1)
    assert "security challenge" in report["failures"][0]


def test_manual_docx_is_hash_pinned_and_uses_official_provenance(tmp_path):
    xml = """<w:document xmlns:w="x"><w:body>
    <w:p><w:r><w:t>Example v Commissioner [2022] HCA 34</w:t></w:r></w:p>
    <w:p><w:r><w:t>[1] This official reason contains a substantive numbered paragraph.</w:t></w:r></w:p>
    </w:body></w:document>"""
    data = BytesIO()
    with ZipFile(data, "w") as archive:
        archive.writestr("word/document.xml", xml)
    manual = tmp_path / "manual"
    manual.mkdir()
    judgment = manual / "judgment.docx"
    judgment.write_bytes(data.getvalue())
    digest = hashlib.sha256(data.getvalue()).hexdigest()
    seeds = tmp_path / "manual.json"
    seeds.write_text(json.dumps([{
        "local_file": "manual/judgment.docx", "official_source_url": "https://www.hcourt.gov.au/example",
        "court": "High Court of Australia", "neutral_citation": "[2022] HCA 34",
        "expected_sha256": digest,
    }]))
    corpus = tmp_path / "court_ready"
    report = pipeline.build_corpus(seeds, corpus)
    assert report["document_count"] == 1
    record_path = next((corpus / "documents").glob("*/*.json"))
    record = json.loads(record_path.read_text())
    assert record["source_url"] == "https://www.hcourt.gov.au/example"
    assert record["provenance"]["raw_sha256"] == digest
