"""Phase 0 gold-set and Phase 2 answer-bearing checks."""

import json
from pathlib import Path

from services.chunker.validation import SourceResolver
from services.evaluation.candidates import (
    BLOCKED_TEXT, passage_dedupe_key, realistic_question, source_class_is_consistent,
)
from services.evaluation.policy import legislation_is_in_scope
from services.evaluation.questions import question_is_sane
from services.evaluation.gold import load_cases
from services.evaluation.gold import validate_gold_set
from services.evaluation.phase2 import golden_fixture_failures
from services.source_registry import normalize_document

ROOT = Path(__file__).resolve().parents[1]
IMPORT = ROOT / "data/imports/ato_ready.json"
IMPORTS = (IMPORT, ROOT / "data/imports/court_ready.json")


def test_gold_set_has_300_source_exact_answer_bearing_cases():
    result = validate_gold_set(
        ROOT / "evals/australia_tax_legal_gold.jsonl",
        SourceResolver(IMPORTS),
    )
    assert result.valid, result.failures


def test_gold_set_rejects_boilerplate_and_covers_abstentions():
    cases = load_cases(ROOT / "evals/australia_tax_legal_gold.jsonl")
    passages = [passage["text"].casefold() for case in cases for passage in case["expected_passages"]]
    assert len(passages) == len(set(passages))
    assert len(passages) == len({passage_dedupe_key(value) for value in passages})
    assert not any(blocked in passage for passage in passages for blocked in BLOCKED_TEXT)
    assert sum(case["must_abstain"] for case in cases) == 10
    assert sum(bool(case["acceptable_alternatives"]) for case in cases) >= 10
    assert [case["id"] for case in cases] == [f"au-tax-{number:04d}" for number in range(1, 301)]


def test_gold_set_excludes_draft_withdrawn_and_unversioned_legislation():
    resolver = SourceResolver(IMPORTS)
    cases = load_cases(ROOT / "evals/australia_tax_legal_gold.jsonl")
    for case in cases:
        for document_id in case["expected_documents"]:
            document = normalize_document(resolver.document(document_id))
            classification = document["classification"]
            assert classification["page_status"] not in {"draft", "withdrawn"}
            if classification["source_class"].startswith("commonwealth_"):
                assert document.get("statute_version")


def test_question_condition_keeps_parenthetical_commas_intact():
    question = realistic_question(
        {"title": "CGT guide", "canonical_reference_id": None},
        {"heading": "Capital proceeds"},
        "If you acquired an asset (for example, shares), you must record its cost base.",
    )
    assert question == "What is the tax treatment when you acquired an asset (for example, shares)?"


def test_question_generation_rejects_dangling_conditions():
    question = realistic_question(
        {"title": "International dealings", "classification": {"source_class": "ato_public_guidance"}},
        {"heading": "Related party dealings"},
        "If during 2020-21, the aggregate amount exceeded five million dollars, answer No.",
    )
    assert "if during" not in question.casefold()
    assert question_is_sane(question)


def test_non_tax_commonwealth_legislation_is_out_of_scope():
    assert not legislation_is_in_scope({
        "title": "Building Energy Efficiency Disclosure Act 2010 - Section 32",
        "classification": {"source_class": "commonwealth_statute"},
    })
    assert legislation_is_in_scope({
        "title": "Income Tax Assessment Act 1997 - Section 8-1",
        "classification": {"source_class": "commonwealth_statute"},
    })


def test_court_decision_accepts_a_medium_neutral_citation():
    assert source_class_is_consistent({
        "title": "Commissioner of Taxation v Example [2025] HCA 30",
        "canonical_reference_id": "[2025] HCA 30",
        "classification": {"source_class": "court_decision", "page_status": "current"},
    })


def test_golden_ready_document_and_chunker_snapshots_pass():
    failures = golden_fixture_failures(
        ROOT / "evals/phase2/golden_ready_document_chunker.jsonl",
        IMPORTS,
    )
    assert not failures, failures


def test_gold_contract_validation_rejects_inconsistencies(tmp_path):
    resolver = SourceResolver(IMPORTS)
    base = json.loads((ROOT / "evals/australia_tax_legal_gold.jsonl").open().readline())

    def check(modified_case):
        path = tmp_path / "case.jsonl"
        path.write_text(json.dumps(modified_case) + "\n")
        return validate_gold_set(path, resolver).failures

    bad_doc = dict(base, expected_documents=["other-doc"])
    assert any("passage document_id missing from expected_documents" in f for f in check(bad_doc))

    bad_ver = dict(base, expected_versions=["other-ver"])
    assert any("passage version_id missing from expected_versions" in f for f in check(bad_ver))

    bad_loc = dict(base, expected_locators=[{"section_id": "other", "char_start": 0, "char_end": 10}])
    assert any("passage locator missing from expected_locators" in f for f in check(bad_loc))
