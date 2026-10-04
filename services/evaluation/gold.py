"""Validation for the source-backed Australian tax/legal gold set."""

from dataclasses import dataclass, field
import hashlib
import json
from pathlib import Path

from services.chunker.core import chunk_document
from services.chunker.validation import SourceResolver
from .candidates import passage_is_substantive, source_class_is_consistent, temporal_is_consistent


GOLD_SIZE = 300
REQUIRED_FIELDS = (
    "id", "question", "category", "expected_jurisdictions", "as_of_date",
    "expected_documents", "expected_versions", "expected_locators",
    "acceptable_alternatives", "must_abstain", "grading_notes", "expected_passages", "review_status",
)


@dataclass
class GoldValidation:
    count: int = 0
    failures: list[str] = field(default_factory=list)

    @property
    def valid(self) -> bool:
        return self.count == GOLD_SIZE and not self.failures


def load_cases(path: Path) -> list[dict]:
    with path.open(encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def _source_passage_failure(case: dict, resolver: SourceResolver) -> str | None:
    passages = case.get("expected_passages")
    if case.get("must_abstain"):
        if passages or case.get("expected_documents") or case.get("expected_versions"):
            return "abstention case has answer evidence"
        return None
    if not isinstance(passages, list) or not passages:
        return "has no expected passage"
    expected_docs = set(case.get("expected_documents", []))
    expected_vers = set(case.get("expected_versions", []))
    locators = {
        (loc.get("section_id"), loc.get("char_start"), loc.get("char_end"))
        for loc in case.get("expected_locators", []) if isinstance(loc, dict)
    }
    for passage in passages:
        doc_id, ver_id = passage.get("document_id"), passage.get("version_id")
        sec_id = passage.get("section_id")
        start, end = passage.get("char_start"), passage.get("char_end")
        if doc_id not in expected_docs:
            return "passage document_id missing from expected_documents"
        if ver_id not in expected_vers:
            return "passage version_id missing from expected_versions"
        if (sec_id, start, end) not in locators:
            return "passage locator missing from expected_locators"
        if not resolver.has_document(doc_id):
            return "references an unknown document"
        document = resolver.document(doc_id)
        if ver_id != (document.get("version") or {}).get("version_id"):
            return "references the wrong version"
        section = next((item for item in document.get("sections", [])
                        if item.get("section_id") == sec_id), None)
        if section is None:
            return "references an unknown section"
        text = section.get("text", "")
        if not isinstance(start, int) or not isinstance(end, int) or not 0 <= start <= end <= len(text):
            return "has an invalid passage span"
        if text[start:end] != passage.get("text"):
            return "passage is not an exact canonical-source span"
        if not source_class_is_consistent(document):
            return "document source class fails authority sanity checks"
        if not passage_is_substantive(document, section, passage["text"]):
            return "passage fails substantive-evidence checks"
        if not temporal_is_consistent(document, passage["text"]):
            return "passage fails temporal-consistency checks"
    return None


def _answer_bearing_failure(case: dict, resolver: SourceResolver) -> str | None:
    if case.get("must_abstain"):
        return None
    for passage in case.get("expected_passages", []):
        _, children = chunk_document(resolver.document(passage["document_id"]))
        bearing = any(
            chunk.get("chunk_type") == "text"
            and (loc := chunk.get("source_locator") or {}).get("section_id") == passage["section_id"]
            and loc.get("char_start", 1) <= passage["char_start"]
            and loc.get("char_end", -1) >= passage["char_end"]
            for chunk in children
        )
        if not bearing:
            return "expected passage is not wholly contained in one child chunk"
    return None


def validate_gold_set(path: Path, resolver: SourceResolver) -> GoldValidation:
    result = GoldValidation()
    cases = load_cases(path)
    result.count = len(cases)
    if len(cases) != GOLD_SIZE:
        result.failures.append(f"expected {GOLD_SIZE} cases, found {len(cases)}")
    seen: set[str] = set()
    for number, case in enumerate(cases, start=1):
        label = case.get("id") or f"line {number}"
        missing = [key for key in REQUIRED_FIELDS if key not in case]
        if missing:
            result.failures.append(f"{label}: missing {', '.join(missing)}")
            continue
        if case["id"] in seen:
            result.failures.append(f"{label}: duplicate id")
        seen.add(case["id"])
        if not isinstance(case["question"], str) or not case["question"].strip():
            result.failures.append(f"{label}: empty question")
        failure = _source_passage_failure(case, resolver)
        if failure:
            result.failures.append(f"{label}: {failure}")
            continue
        if case.get("category") == "historical_as_at" and not case.get("as_of_date"):
            result.failures.append(f"{label}: historical_as_at case must declare an as_of_date")
        failure = _answer_bearing_failure(case, resolver)
        if failure:
            result.failures.append(f"{label}: {failure}")
    return result


def gold_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()
