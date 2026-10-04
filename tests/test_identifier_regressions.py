"""Regression coverage for canonical ruling identifiers."""

from services.source_registry.identifiers import normalize_document


def test_new_rule_reprocesses_prior_resolution_from_original_evidence():
    document = {
        "document_id": "ruling", "title": "Taxation Ruling TR 96/11",
        "source_url": "https://www.ato.gov.au/law/view/pdf/pbr/tr1996-011.pdf",
        "canonical_reference_id": "TR 1996/11",
        "canonical_reference": {
            "original": "TR 19/96", "resolution": "normalized",
            "evidence": "source_url", "rule_version": "citation-evidence-v2",
        },
    }
    normalized = normalize_document(document)
    assert normalized["canonical_reference_id"] == "TR 96/11"
    assert normalized["canonical_reference"]["rule_version"] == "citation-evidence-v3"


def test_compact_pre_2000_docid_keeps_the_two_digit_year():
    document = {
        "document_id": "determination", "title": "Taxation Determination",
        "source_url": "https://www.ato.gov.au/law/view/document?docid=TXD%2FTD93217%2FNAT",
        "canonical_reference_id": "TD 93/217",
    }
    normalized = normalize_document(document)
    assert normalized["canonical_reference_id"] == "TD 93/217"
    assert normalized["canonical_reference"]["evidence"] == "source_url"
    assert normalized["canonical_reference"]["resolution"] == "confirmed"


def test_mismatched_compact_docid_is_flagged_not_uncorroborated():
    document = {
        "document_id": "determination", "title": "Taxation Determination",
        "source_url": "https://www.ato.gov.au/law/view/document?docid=TXD%2FTD93217%2FNAT",
        "canonical_reference_id": "TD 93/218",
    }
    normalized = normalize_document(document)
    assert normalized["canonical_reference_id"] is None
    assert normalized["canonical_reference"]["resolution"] == "flagged"
    assert normalized["canonical_reference"]["evidence"] == "number mismatch"

