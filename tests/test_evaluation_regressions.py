"""Regression tests for benchmark candidate and question quality."""

from services.evaluation.candidates import (
    applicable_as_of,
    passage_is_substantive,
    source_class_is_consistent,
    temporal_is_consistent,
)
from services.evaluation.benchmark_corrections import apply_benchmark_correction
from services.evaluation.questions import question_is_sane, realistic_question


def _authority(source_class: str, reference: str, title: str = "Tax guidance") -> dict:
    return {
        "title": title,
        "canonical_reference_id": reference,
        "classification": {"source_class": source_class, "page_status": "current"},
    }


def test_ruling_classes_require_their_canonical_reference_prefix():
    assert not source_class_is_consistent(
        _authority("taxation_determination", "TR 93/30", "Title mentions TD 1999/66")
    )
    assert not source_class_is_consistent(_authority("law_companion_ruling", "PCG 2019/6"))
    assert source_class_is_consistent(_authority("law_companion_ruling", "LCR 2021/2"))
    assert not source_class_is_consistent(_authority("ato_public_guidance", "TR 2022/3"))


def test_substantive_passage_must_start_at_a_boundary():
    document = {"title": "Deductions", "classification": {}}
    section = {"heading": "Eligibility requirements"}
    tail = (" taxpayers satisfy distinct eligibility requirements and retain reliable records "
            "showing expenses incurred for producing assessable income under the relevant rule "
            "during each applicable income year with supporting evidence available for review.")
    assert not passage_is_substantive(document, section, "ill be protected when" + tail)
    assert passage_is_substantive(document, section, "Taxpayers will be protected when" + tail)


def test_latest_annual_period_is_the_shared_temporal_anchor():
    document = {"classification": {"applicable_periods": ["2007-08", "2011-12"]}}
    assert applicable_as_of(document) == "2012-06-30"
    assert temporal_is_consistent(document, "The requirements apply throughout 2011.")


def test_annual_period_before_authority_issue_year_is_not_an_as_of_date():
    document = {
        "canonical_reference_id": "TR 2022/3",
        "classification": {"applicable_periods": ["2018-19", "2019-20"]},
    }
    assert applicable_as_of(document) is None


def test_numeric_definition_fragment_is_not_substantive_evidence():
    document = {"title": "Income Tax Assessment Act 1997", "classification": {}}
    passage = ("715-130 and 715-185, has the meaning given by section 715-145 and applies "
               "to an equity or loan interest for determining consequences of a direct value "
               "shift under the relevant statutory provisions and associated operative rules.")
    for heading in ("Definition: 715-130 and 715-185,", "995-1 Definition: 715-130 and 715-185,"):
        section = {"heading_path": ["Act", heading]}
        assert not passage_is_substantive(document, section, passage)


def test_question_templates_use_whole_word_modals_and_one_question_mark():
    document = {"title": "Stapled securities", "classification": {"source_class": "ato_public_guidance"}}
    cannot = realistic_question(document, {"heading": "Stapled securities"},
                                "The asset cannot be sold separately from the arrangement.")
    assert not cannot.startswith("When may")
    question = realistic_question(document, {"heading": "Transport expenses?"},
                                  "A taxpayer may claim qualifying transport expenses.")
    assert question.endswith("?") and not question.endswith("??")
    assert not question_is_sane("What tax treatment applies to transport expenses??")


def test_ruling_reliance_and_part_ivaaa_boilerplate_is_rejected():
    document = {"title": "Taxation Ruling", "classification": {}}
    section = {"heading": "Ruling"}
    passages = [
        "If this Ruling applies to you, and you correctly rely on it, we will apply the law to you in the way set out in this Ruling.",
        "This Ruling, to the extent that it is capable of being a 'public ruling' in terms of Part IVAAA of the Taxation Administration Act 1953 , is a public ruling for the purposes of that Part.",
    ]
    for p in passages:
        assert not passage_is_substantive(document, section, p)


def test_passage_matching_title_or_contained_in_question_is_rejected():
    title = "TD 93/202 - Income tax: Offshore Banking Units (OBU) - can an OBU use offshore banking (OB) money for other purposes?"
    document = {"title": title, "classification": {"source_class": "taxation_determination"}}
    section = {"heading": title}
    assert not passage_is_substantive(document, section, title)


def test_historical_guidance_preserves_period_as_of_date():
    document = {
        "title": "C Salary and wages",
        "dates": {"published": "2019-02-13"},
        "classification": {
            "source_class": "ato_public_guidance",
            "historical_guidance": True,
            "applicable_periods": ["2011-12"],
        },
    }
    assert applicable_as_of(document) == "2012-06-30"


def test_confirmed_benchmark_corrections_are_bound_to_expected_authorities():
    case = {
        "id": "au-tax-0026",
        "question": "What ATO guidance applies to Practical compliance guideline?",
        "expected_documents": ["dd328bba-f360-5dca-aae9-5be62d5e5727"],
    }
    corrected = apply_benchmark_correction(case)
    assert corrected["question"].startswith("What earlier professional-firm")
    assert case["question"] != corrected["question"]


def test_part_year_correction_rebinds_the_answer_bearing_span():
    case = {
        "id": "au-tax-0011",
        "question": "What is the tax treatment?",
        "expected_documents": ["45e7c337-3496-5cc0-868e-786e348bc760"],
        "expected_passages": [{"document_id": "45e7c337-3496-5cc0-868e-786e348bc760",
                               "version_id": "v1", "section_id": "sec_0013",
                               "char_start": 1, "char_end": 2, "text": "x"}],
        "expected_locators": [], "acceptable_alternatives": ["old"],
    }
    corrected = apply_benchmark_correction(case)
    passage = corrected["expected_passages"][0]
    assert passage["section_id"] == "sec_0014"
    assert (passage["char_start"], passage["char_end"]) == (0, 576)
    assert corrected["expected_locators"] == [{"section_id": "sec_0014",
                                                "char_start": 0, "char_end": 576}]
