"""Regression tests for official judgment parsing edge cases."""

from io import BytesIO
from zipfile import ZipFile

from services.court_ingestion.parser import parse_judgment


HTML = b"""<html><head><title>Commissioner v Example [2024] FCA 123</title></head><body>
<p>Judgment delivered 12 March 2024</p>
<p>[1] This judgment paragraph contains enough words for the parser.</p>
</body></html>"""


def test_parser_prefers_labelled_judgment_date_over_hearing_date():
    body = HTML.replace(
        b"Judgment delivered 12 March 2024",
        b"Hearing date 14 May 2023</p><p>Judgment delivered on 12 March 2024",
    )
    assert parse_judgment(body, "[2024] FCA 123").decision_date == "12 March 2024"


def test_pdf_paragraphs_reject_out_of_order_numbers_and_keep_citations(monkeypatch):
    blocks = [
        "Example v Commissioner [2025] HCA 30",
        "1 This substantive opening paragraph contains enough words to retain.",
        "12 See the footnote authority that is not paragraph twelve.",
        "[2019] HCA 36 at [12] supports the conclusion in this paragraph.",
        "2 This second substantive paragraph also contains enough words to retain.",
    ]
    monkeypatch.setattr("services.court_ingestion.parser._document_blocks",
                        lambda body, content_type: (blocks[0], blocks))
    parsed = parse_judgment(b"pdf", "[2025] HCA 30", "application/pdf")
    assert [number for number, _ in parsed.paragraphs] == [1, 2]
    assert "12 See the footnote" in parsed.paragraphs[0][1]
    assert "[2019] HCA 36" in parsed.paragraphs[0][1]


def test_docx_judgment_decodes_xml_entities():
    xml = """<w:document xmlns:w="x"><w:body>
    <w:p><w:r><w:t>Example Pty Ltd &amp; Ors v Commissioner [2022] HCA 34</w:t></w:r></w:p>
    <w:p><w:r><w:t>[1] Example Pty Ltd &amp; Ors made the relevant application.</w:t></w:r></w:p>
    </w:body></w:document>"""
    data = BytesIO()
    with ZipFile(data, "w") as archive:
        archive.writestr("word/document.xml", xml)
    parsed = parse_judgment(data.getvalue(), "[2022] HCA 34",
                            "application/vnd.openxmlformats-officedocument.wordprocessingml.document")
    assert "Pty Ltd & Ors" in parsed.title
    assert "Pty Ltd & Ors" in parsed.paragraphs[0][1]
