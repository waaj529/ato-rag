from services.answering.query_normalization import expand_official_acronyms


def test_expands_standalone_ato_acronym() -> None:
    assert expand_official_acronyms("what is ato?") == (
        "what is Australian Taxation Office (ATO)?"
    )


def test_does_not_change_unrelated_text() -> None:
    assert expand_official_acronyms("What is GST?") == "What is GST?"


def test_does_not_expand_an_already_canonical_ato_name() -> None:
    query = "What is the Australian Taxation Office (ATO)?"
    assert expand_official_acronyms(query) == query
