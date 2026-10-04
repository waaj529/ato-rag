"""Evidence-bound corrections for confirmed benchmark defects."""


CORRECTIONS = {
    "au-tax-0011": {
        "document_id": "45e7c337-3496-5cc0-868e-786e348bc760",
        "section_id": "sec_0014",
        "question": (
            "When can a taxpayer claim only part of the base amount for a dependent "
            "child or student for 2024–25, and how is the reduced amount worked out?"
        ),
        "char_start": 0,
        "char_end": 576,
        "text": (
            "You can claim only part of the base amount for dependent children or students if either:\n\n"
            "- the child or student is treated as an Australian resident for only part of 2024–25\n"
            "- the student is under 25 years old and in full-time education for only part of 2024–25\n"
            "- the child or student is maintained by you for only part of 2024–25\n"
            "- the child is 21 years old at 30 June 2025 and not in full-time education\n"
            "- the student is 25 years old at 30 June 2025.\n\n"
            "Use worksheet 1 to work out the reduced base amount for each eligible dependent "
            "child or student as described in table 2."
        ),
    },
    "au-tax-0026": {
        "document_id": "dd328bba-f360-5dca-aae9-5be62d5e5727",
        "question": (
            "What earlier professional-firm profit-allocation guidance did PCG 2021/4 "
            "replace, and why had the earlier guidance been suspended?"
        ),
    },
    "au-tax-0040": {
        "document_id": "7ad83b0d-8398-5a1a-87e4-d9aabc997556",
        "question": (
            "What is a converted CFC loss, and for which statutory accounting periods is "
            "it treated as a loss under Part X of the ITAA 1936?"
        ),
    },
    "au-tax-0069": {
        "document_id": "leg-c2026c00324-293-1-ddddaf1e",
        "question": (
            "What does Division 293 of the Income Tax Assessment Act 1997 do, and what "
            "high-income threshold does section 293-1 state?"
        ),
    },
    "au-tax-0084": {
        "document_id": "leg-c2026c00324-820-740-3b5adfcc",
        "question": (
            "What control concepts and calculation method does section 820-740 of the "
            "Income Tax Assessment Act 1997 say the Subdivision covers?"
        ),
    },
}


def apply_benchmark_correction(case: dict) -> dict:
    """Apply a reviewed correction only when its expected authority still matches."""
    correction = CORRECTIONS.get(case["id"])
    if correction is None:
        return case
    if case.get("expected_documents") != [correction["document_id"]]:
        raise RuntimeError(f"{case['id']} correction no longer matches its authority")
    corrected = {**case, "question": correction["question"]}
    if "text" not in correction:
        return corrected
    passage = {**case["expected_passages"][0],
               "section_id": correction["section_id"],
               "char_start": correction["char_start"],
               "char_end": correction["char_end"],
               "text": correction["text"]}
    corrected["expected_passages"] = [passage]
    corrected["expected_locators"] = [{key: passage[key]
                                        for key in ("section_id", "char_start", "char_end")}]
    corrected["acceptable_alternatives"] = []
    return corrected
