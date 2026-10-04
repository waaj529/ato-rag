"""Tests for source authority taxonomy and lifecycle normalization."""

from services.source_registry.authority import normalize_authority


def test_draft_and_withdrawn_rulings_are_not_binding():
    draft = normalize_authority({
        "title": "Draft Taxation Ruling TR 2012/D1",
        "canonical_reference_id": "TR 2012/D1",
        "classification": {"source_class": "public_ruling", "page_status": "draft",
                           "binding_effect": "binding_on_commissioner", "authority_rank": 20},
    })
    withdrawn = normalize_authority({
        "title": "TD 96/39W - Notice of Withdrawal",
        "classification": {"source_class": "taxation_determination", "page_status": "current",
                           "binding_effect": "binding_on_commissioner", "authority_rank": 20},
    })
    assert draft["classification"]["binding_effect"] == "non_binding_draft"
    assert withdrawn["classification"]["page_status"] == "withdrawn"
    assert withdrawn["classification"]["binding_effect"] == "withdrawn"


def test_ato_mirror_legislation_and_misclassified_guidance_are_separated():
    act = normalize_authority({
        "title": "Income Tax Assessment Act 1997",
        "source_url": "https://www.ato.gov.au/law/view/document?docid=PAC%2F19970038%2F1-1",
        "classification": {"source_class": "primary_legislation", "document_type": "Act / Law",
                           "page_status": "current", "binding_effect": "binding_law"},
    })
    guide = normalize_authority({
        "title": "Fringe benefits tax - a guide for employers",
        "source_url": "https://www.ato.gov.au/businesses-and-organisations/example",
        "classification": {"source_class": "primary_legislation", "document_type": "Act / Law",
                           "page_status": "current", "binding_effect": "binding_law"},
    })
    assert act["classification"]["source_class"] == "commonwealth_statute"
    assert guide["classification"]["source_class"] == "ato_public_guidance"
    assert guide["classification"]["binding_effect"] == "non_binding_guidance"
