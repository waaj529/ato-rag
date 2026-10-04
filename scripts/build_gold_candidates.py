#!/usr/bin/env python3
"""Build a conservative, source-backed Phase 0 benchmark candidate set."""

from collections import defaultdict
import gzip
import hashlib
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from services.evaluation.candidates import (
    applicable_as_of, extract_substantive_passage, passage_dedupe_key, realistic_question,
)
from services.evaluation.benchmark_corrections import apply_benchmark_correction
from services.evaluation.questions import question_is_sane
from services.source_registry import normalize_document


MANIFESTS = (ROOT / "data/imports/ato_ready.json", ROOT / "data/imports/court_ready.json")
OUTPUT = ROOT / "evals/australia_tax_legal_gold.jsonl"
QUOTAS = {
    "ato_public_guidance": 61, "commonwealth_statute": 100,
    "commonwealth_regulation": 10, "public_ruling": 50,
    "taxation_determination": 20,
    "law_companion_ruling": 20, "practical_compliance_guideline": 20,
    "court_decision": 9,
}
ABSTENTIONS = (
    "What does TR 2099/999 provide about income tax?",
    "What does section 999-999 of the ITAA 1997 provide?",
    "What does [2099] HCA 999 decide about CGT?",
    "What does PCG 2099/99 say about Division 7A?",
    "What does TD 2099/99 determine about GST?",
    "What does section 0-0 of the Taxation Administration Act 1953 provide?",
    "What does GSTR 2099/99 say about supplies?",
    "What does LCR 2099/99 say about deductions?",
    "What does CR 2099/99 decide about fringe benefits tax?",
    "What does the nonexistent Income Tax Assessment Act 2099 provide?",
)


def _rank(document_id: str) -> str:
    return hashlib.sha256(f"benchmark-v3:{document_id}".encode()).hexdigest()


def _category(source_class: str, document: dict, as_of_date: str | None = None) -> str:
    if source_class in {"commonwealth_statute", "commonwealth_regulation"}:
        return "exact_section_lookup"
    if (document.get("classification") or {}).get("historical_guidance"):
        return "historical_as_at" if as_of_date else ("statutory_concept_paraphrase"
                                                       if source_class == "ato_public_guidance"
                                                       else "authority_lookup")
    return "statutory_concept_paraphrase" if source_class == "ato_public_guidance" else "authority_lookup"


def _alternatives(document: dict, passage: str) -> list[str]:
    return sorted({str(reference["reference"]) for reference in document.get("references") or []
                   if reference.get("reference") and str(reference["reference"]).casefold() in passage.casefold()})


def _answer_case(number: int, document: dict, extracted: tuple) -> dict:
    section, text, start, end = extracted
    passage = {"document_id": document["document_id"], "version_id": document["version"]["version_id"],
               "section_id": section["section_id"], "char_start": start, "char_end": end, "text": text}
    source_class = document["classification"]["source_class"]
    as_of = applicable_as_of(document)
    return {"id": f"au-tax-{number:04d}", "question": realistic_question(document, section, text),
            "category": _category(source_class, document, as_of),
            "expected_jurisdictions": ["AU-COMMONWEALTH"], "as_of_date": as_of,
            "expected_documents": [document["document_id"]],
            "expected_versions": [document["version"]["version_id"]],
            "expected_locators": [{key: passage[key] for key in ("section_id", "char_start", "char_end")}],
            "acceptable_alternatives": _alternatives(document, text), "must_abstain": False,
            "grading_notes": "Pass only if retrieval returns a child containing the exact expected passage.",
            "expected_passages": [passage], "review_status": "pending_domain_review"}


def _abstention_case(number: int, question: str) -> dict:
    return {"id": f"au-tax-{number:04d}", "question": question, "category": "deliberately_malformed_citation",
            "expected_jurisdictions": ["AU-COMMONWEALTH"], "as_of_date": None, "expected_documents": [],
            "expected_versions": [], "expected_locators": [], "acceptable_alternatives": [], "must_abstain": True,
            "grading_notes": "Must abstain: the cited authority is deliberately absent from this corpus.",
            "expected_passages": [], "review_status": "pending_domain_review"}


def main() -> int:
    candidates = defaultdict(list)
    for manifest_path in MANIFESTS:
        manifest = json.loads(manifest_path.read_text())
        with gzip.open(manifest["inventory_path"], "rt", encoding="utf-8") as handle:
            for line in handle:
                entry = json.loads(line)
                document = normalize_document(json.loads(
                    (Path(manifest["source_root"]) / entry["relative_path"]).read_text()
                ))
                source_class = (document.get("classification") or {}).get("source_class")
                extracted = extract_substantive_passage(document) if source_class in QUOTAS else None
                if extracted and question_is_sane(realistic_question(document, extracted[0], extracted[1])):
                    candidates[source_class].append((_rank(document["document_id"]), document, extracted))
    selected, seen, seen_questions = [], set(), set()
    for source_class, quota in QUOTAS.items():
        matches = 0
        for _, document, extracted in sorted(candidates[source_class]):
            question = realistic_question(document, extracted[0], extracted[1]).casefold()
            key = passage_dedupe_key(extracted[1])
            if key not in seen and question not in seen_questions:
                selected.append((document, extracted)); seen.add(key)
                seen_questions.add(question); matches += 1
            if matches == quota:
                break
        if matches != quota:
            raise RuntimeError(f"not enough substantive {source_class} candidates")
    cases = [apply_benchmark_correction(_answer_case(number, *item))
             for number, item in enumerate(selected, 1)]
    first_abstention = len(cases)
    cases.extend(_abstention_case(first_abstention + number, question)
                 for number, question in enumerate(ABSTENTIONS, 1))
    OUTPUT.write_text("".join(json.dumps(case, ensure_ascii=False) + "\n" for case in cases))
    print(f"wrote {len(cases)} candidates to {OUTPUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
