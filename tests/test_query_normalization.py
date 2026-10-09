from services.answering.query_normalization import expand_official_acronyms


def test_expands_standalone_ato_acronym() -> None:
    assert expand_official_acronyms("what is ato?") == (
        "what is Australian Taxation Office (ATO)?"
    )


def test_does_not_change_unrelated_text() -> None:
    assert expand_official_acronyms("What is GST?") == "What is GST?"
