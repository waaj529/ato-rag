"""Frozen ready-document/chunker regression validation for the Phase 2 gate."""

import gzip
import hashlib
import json
from pathlib import Path

from services.chunker.core import chunk_document
from services.source_registry import normalize_document

REQUIRED_COVERAGE = {
    "source_class:ato_public_guidance", "source_class:commonwealth_statute",
    "source_class:commonwealth_regulation", "source_class:public_ruling",
    "source_class:taxation_determination", "source_class:law_companion_ruling",
    "source_class:practical_compliance_guideline", "source_class:court_decision",
    "feature:structured_table", "feature:historical_guidance", "feature:long_section",
}


def _digest(values: list[str]) -> str:
    return hashlib.sha256("\n".join(values).encode()).hexdigest()


def _source_failures(fixture: dict, document: dict) -> list[str]:
    expected = fixture["expected_source"]
    sections = document.get("sections") or []
    failures = []
    actual = {
        "source_class": (document.get("classification") or {}).get("source_class"),
        "section_count": len(sections),
        "table_count": len(document.get("tables") or []),
        "first_section_id": sections[0].get("section_id") if sections else None,
        "first_heading_path": sections[0].get("heading_path") or [] if sections else [],
        "first_section_sha256": hashlib.sha256(
            (sections[0].get("text", "") if sections else "").encode()
        ).hexdigest(),
    }
    for key, value in expected.items():
        if actual[key] != value:
            failures.append(f"source {key} changed")
    return failures


def _chunk_failures(fixture: dict, document: dict) -> list[str]:
    parents, children = chunk_document(document)
    actual = {
        "parent_count": len(parents), "child_count": len(children),
        "parent_ids_sha256": _digest([item["parent_id"] for item in parents]),
        "chunk_ids_sha256": _digest([item["chunk_id"] for item in children]),
        "text_children": sum(item["chunk_type"] == "text" for item in children),
        "table_children": sum(item["chunk_type"] == "table" for item in children),
    }
    failures = [f"chunk {key} changed" for key, value in fixture["expected_chunks"].items()
                if actual[key] != value]
    passage = fixture["expected_passage"]
    section = next((s for s in (document.get("sections") or [])
                    if s.get("section_id") == passage.get("section_id")), None)
    if section is None:
        failures.append("expected passage section missing from document")
    elif section.get("text", "")[passage["char_start"]:passage["char_end"]] != passage.get("text"):
        failures.append("expected passage text does not match canonical source")
    bearing = any(
        child["chunk_type"] == "text"
        and child["source_locator"]["section_id"] == passage["section_id"]
        and child["source_locator"]["char_start"] <= passage["char_start"]
        and child["source_locator"]["char_end"] >= passage["char_end"]
        for child in children
    )
    if not bearing:
        failures.append("expected passage is not answer-bearing")
    return failures


def golden_fixture_failures(path: Path, manifests: tuple[Path, ...]) -> list[str]:
    failures = []
    roots, inventories = {}, {}
    for m in manifests:
        data = json.loads(m.read_text())
        roots[m.name] = Path(data["source_root"])
        with gzip.open(data["inventory_path"], "rt", encoding="utf-8") as handle:
            inventories[m.name] = {
                entry["relative_path"]: entry.get("file_sha256")
                for entry in (json.loads(line) for line in handle)
            }
    with path.open(encoding="utf-8") as handle:
        fixtures = [json.loads(line) for line in handle if line.strip()]
    seen_ids: set[str] = set()
    coverage_set: set[str] = set()
    for fixture in fixtures:
        fid = fixture.get("fixture_id")
        if not fid or fid in seen_ids:
            failures.append(f"duplicate or missing fixture_id: {fid}")
        seen_ids.add(fid)
        coverage_set.add(fixture.get("coverage", ""))
    if coverage_set != REQUIRED_COVERAGE:
        missing = sorted(REQUIRED_COVERAGE - coverage_set)
        failures.append(f"fixture coverage mismatch; missing: {missing}")
    for fixture in fixtures:
        label = fixture.get("fixture_id", "unknown")
        manifest_name = fixture.get("source_manifest")
        source_root = roots.get(manifest_name)
        if source_root is None:
            failures.append(f"{label}: unknown source manifest")
            continue
        rel_path = fixture.get("relative_path")
        indexed_hash = inventories.get(manifest_name, {}).get(rel_path)
        if indexed_hash is None:
            failures.append(f"{label}: source file not indexed in manifest inventory")
            continue
        if indexed_hash != fixture["file_sha256"]:
            failures.append(f"{label}: manifest inventory file hash mismatch")
            continue
        source_path = source_root / rel_path
        raw = source_path.read_bytes()
        if hashlib.sha256(raw).hexdigest() != fixture["file_sha256"]:
            failures.append(f"{label}: source file hash changed")
            continue
        document = normalize_document(json.loads(raw))
        if document.get("document_id") != fixture["document_id"]:
            failures.append(f"{label}: document id changed")
        if (document.get("version") or {}).get("version_id") != fixture["version_id"]:
            failures.append(f"{label}: version id changed")
        scoped = _source_failures(fixture, document) + _chunk_failures(fixture, document)
        failures.extend(f"{label}: {failure}" for failure in scoped)
    return failures
