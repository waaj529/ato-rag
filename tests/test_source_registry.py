"""Tests for citation resolution and legislation section identity."""

from services.source_registry.identifiers import normalize_document, resolve_citation
from services.source_registry.sections import normalize_section_ids

PDF_URL = ("https://www.ato.gov.au/law/view/pdf?DocID=TXR%2FTR20062%2FNAT%2FATO%2F00001"
           "&PiT=99991231235958&filename=law%2Fview%2Fpdf%2Fpbr%2Ftr2006-002.pdf")


def test_split_year_citation_is_repaired_from_source_url_evidence():
    document = {
        "document_id": "60dbd042-cdc8-5619-8d55-1b0e07af8d5d",
        "title": "Taxation Ruling TR 2006/2",
        "source_url": PDF_URL,
        "canonical_reference_id": "TR 20/06",
    }
    citation = resolve_citation(document)
    assert citation.resolution == "normalized"
    assert citation.value == "TR 2006/2"
    assert citation.original == "TR 20/06"
    assert citation.evidence == "source_url"
    assert normalize_document(document)["canonical_reference_id"] == "TR 2006/2"


def test_legitimate_pre_2000_citation_is_left_alone():
    # A two-digit year that is a *suffix* of the source year is the real pre-2000 form.
    document = {
        "document_id": "d1",
        "title": "Income tax: deductions for something",
        "source_url": PDF_URL.replace("tr2006-002", "tr1997-025"),
        "canonical_reference_id": "TR 97/25",
    }
    citation = resolve_citation(document)
    assert citation.resolution == "confirmed"
    assert citation.value == "TR 97/25"
    assert normalize_document(document)["canonical_reference_id"] == "TR 97/25"


def test_citation_named_verbatim_in_its_title_is_confirmed_untouched():
    document = {
        "document_id": "d2",
        "title": "Taxation Ruling TR 97/25",
        "source_url": PDF_URL.replace("tr2006-002", "tr1997-025"),
        "canonical_reference_id": "TR 97/25",
    }
    citation = resolve_citation(document)
    assert (citation.resolution, citation.value, citation.evidence) == (
        "confirmed", "TR 97/25", "title+source_url")


def test_evidence_contradicting_a_citation_drops_it_rather_than_guessing():
    document = {
        "document_id": "ab4ead4f-7155-55ff-a891-12f12d7fb0f9",
        "title": "Goods and services tax: something unrelated to the stored citation",
        "source_url": PDF_URL.replace("tr2006-002", "gstr2012-003"),
        "canonical_reference_id": "TR 20/12",
    }
    citation = resolve_citation(document)
    assert citation.resolution == "flagged"
    assert citation.value is None
    assert citation.original == "TR 20/12"
    assert normalize_document(document)["canonical_reference_id"] is None


def test_citation_without_url_evidence_is_retained_not_blanked():
    document = {
        "document_id": "d3",
        "title": "Class Ruling",
        "source_url": "https://www.ato.gov.au/law/view/document?docid=COG%2FCLASSRULING",
        "canonical_reference_id": "CR 2026/61",
    }
    citation = resolve_citation(document)
    assert citation.resolution == "uncorroborated"
    assert citation.value == "CR 2026/61"
    assert normalize_document(document)["canonical_reference_id"] == "CR 2026/61"


def test_compact_law_view_docid_repairs_a_split_year_citation():
    document = {
        "document_id": "d6", "title": "Miscellaneous Taxation Ruling",
        "source_url": "https://www.ato.gov.au/law/view/document?docid=MXR%2FMT20123%2FNAT",
        "canonical_reference_id": "MT 20/123",
    }
    citation = resolve_citation(document)
    assert (citation.resolution, citation.value) == ("normalized", "MT 2012/3")


def test_identifiers_outside_the_rule_scope_are_not_evaluated():
    document = {"document_id": "d4", "title": "Corporations Act 2001",
                "source_url": "https://www.legislation.gov.au/C2004A05128/latest/text",
                "canonical_reference_id": "C2004A05128"}
    citation = resolve_citation(document)
    assert (citation.resolution, citation.value) == ("not_evaluated", "C2004A05128")


def legislation_document(**overrides):
    document = {
        "document_id": "leg-c2026c00280-1-1-350c2f64",
        "title": "Corporations Act 2001 Section 1-1 (Short title)",
        "source_url": "https://www.legislation.gov.au/C2004A05128/latest/text#1-1",
        "statute_version": {"register_id": "C2026C00280"},
        "sections": [{"section_id": "sec_0001", "text": "This Act may be cited..."}],
    }
    document.update(overrides)
    return document


def test_legislation_section_id_is_derived_and_upstream_value_preserved():
    normalized = normalize_section_ids(legislation_document())
    assert normalized["section_id_resolution"]["value"] == "C2026C00280#1-1"
    section = normalized["sections"][0]
    assert section["section_id"] == "C2026C00280#1-1"
    assert section["source_section_id"] == "sec_0001"


def test_legislation_section_id_is_withheld_when_sources_disagree():
    document = legislation_document(statute_version={"register_id": "C2026C00999"})
    assert normalize_section_ids(document) is document


def test_non_legislation_sections_are_untouched():
    document = {"document_id": "d5", "sections": [{"section_id": "sec_0001", "text": "x"}]}
    assert normalize_section_ids(document) is document


def test_normalising_an_already_normalised_document_changes_nothing():
    # Both the chunk pipeline and the source resolver apply this, so it must be idempotent.
    legislation = normalize_document(legislation_document())
    assert normalize_document(legislation) == legislation
    ruling = normalize_document({
        "document_id": "60dbd042-cdc8-5619-8d55-1b0e07af8d5d",
        "title": "Taxation Ruling TR 2006/2", "source_url": PDF_URL,
        "canonical_reference_id": "TR 20/06",
        "sections": [{"section_id": "sec_0001", "text": "x"}],
    })
    assert normalize_document(ruling) == ruling
