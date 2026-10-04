"""Tests for source-URL identity and duplicate index-row conflict detection."""

from services.source_registry.conflicts import conflict_report
from services.source_registry.urls import normalize_source_url

PDF_URL = ("https://www.ato.gov.au/law/view/pdf?DocID=GST%2FGSTR20033%2FNAT%2FATO%2F00001"
           "&PiT=99991231235958&filename=law%2Fview%2Fpdf%2Fpbr%2Fgstr2003-003c5.pdf")


def test_source_url_key_ignores_query_parameter_case():
    mixed = PDF_URL.replace("DocID=", "DocId=")
    assert PDF_URL != mixed
    assert normalize_source_url(PDF_URL) == normalize_source_url(mixed)


def test_source_url_key_distinguishes_different_sources():
    other = PDF_URL.replace("gstr2003-003c5", "gstr2003-004c5")
    assert normalize_source_url(PDF_URL) != normalize_source_url(other)


def test_legislation_url_fragment_survives_normalisation():
    base = "https://www.legislation.gov.au/C2004A05128/latest/text"
    assert normalize_source_url(f"{base}#1-1") != normalize_source_url(f"{base}#1-7")


def test_documents_without_a_source_url_are_counted_not_grouped():
    report = conflict_report([(None, "v1", "aaa"), ("", "v1", "bbb")])
    assert report["documents_without_source_url"] == 2
    assert report["source_url_groups"] == 0
    assert report["conflicting_source_urls"] == 0


def test_duplicate_rows_agreeing_on_one_version_are_not_a_conflict():
    report = conflict_report([("https://x/1", "v1", "aaa"), ("https://x/1", "v1", "aaa")])
    assert report["conflicting_source_urls"] == 0
    assert report["duplicate_source_url_rows"] == 1
    assert report["source_url_groups"] == 1


def test_one_version_claimed_with_two_different_contents_is_a_conflict():
    report = conflict_report([("https://x/1", "v1", "aaa"), ("https://x/1", "v1", "bbb")])
    assert report["conflicting_source_urls"] == 1
    assert report["source_url_conflicts"] == [{"source_url": "https://x/1", "version_id": "v1"}]


def test_distinct_versions_of_one_source_are_legitimate_re_captures():
    report = conflict_report([("https://x/1", "v1", "aaa"), ("https://x/1", "v2", "bbb")])
    assert report["conflicting_source_urls"] == 0
    assert report["duplicate_source_url_rows"] == 1
