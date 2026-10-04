#!/usr/bin/env python3
"""Freeze representative ready-document and chunk outputs for regression tests."""

import gzip
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from services.chunker.core import chunk_document
from services.chunker.text import token_count
from services.source_registry import normalize_document

MANIFESTS = (
    ROOT / "data/imports/ato_ready.json",
    ROOT / "data/imports/court_ready.json",
)
COURT_MANIFEST = MANIFESTS[1]
OUTPUT = ROOT / "evals/phase2/golden_ready_document_chunker.jsonl"
SOURCE_CLASSES = (
    "ato_public_guidance", "commonwealth_statute", "commonwealth_regulation",
    "public_ruling", "taxation_determination",
    "law_companion_ruling", "practical_compliance_guideline", "court_decision",
)


def _rank(label: str, document_id: str) -> str:
    return hashlib.sha256(f"phase2-golden:{label}:{document_id}".encode()).hexdigest()


def _digest(values: list[str]) -> str:
    return hashlib.sha256("\n".join(values).encode()).hexdigest()


def _selectors(document: dict) -> list[str]:
    classification = document.get("classification") or {}
    labels = [f"source_class:{classification.get('source_class')}"]
    if document.get("tables"):
        labels.append("feature:structured_table")
    if classification.get("historical_guidance"):
        labels.append("feature:historical_guidance")
    if any(token_count(section.get("text", "")) > 900 for section in document.get("sections", [])):
        labels.append("feature:long_section")
    return labels


def _snapshot(label: str, manifest: Path, entry: dict, document: dict) -> dict:
    parents, children = chunk_document(document)
    section = document["sections"][0]
    child = next(item for item in children if item["chunk_type"] == "text")
    locator = child["source_locator"]
    passage_text = child["text"][:400].rstrip()
    source = {
        "source_class": (document.get("classification") or {}).get("source_class"),
        "section_count": len(document.get("sections") or []),
        "table_count": len(document.get("tables") or []),
        "first_section_id": section.get("section_id"),
        "first_heading_path": section.get("heading_path") or [],
        "first_section_sha256": hashlib.sha256(section.get("text", "").encode()).hexdigest(),
    }
    chunks = {
        "parent_count": len(parents), "child_count": len(children),
        "parent_ids_sha256": _digest([item["parent_id"] for item in parents]),
        "chunk_ids_sha256": _digest([item["chunk_id"] for item in children]),
        "text_children": sum(item["chunk_type"] == "text" for item in children),
        "table_children": sum(item["chunk_type"] == "table" for item in children),
    }
    passage = {
        "section_id": locator["section_id"],
        "char_start": locator["char_start"],
        "char_end": locator["char_start"] + len(passage_text),
        "text": passage_text,
    }
    return {
        "fixture_id": label.replace(":", "-"), "coverage": label,
        "source_manifest": manifest.name,
        "relative_path": entry["relative_path"], "file_sha256": entry["file_sha256"],
        "document_id": document["document_id"],
        "version_id": document["version"]["version_id"],
        "title": document["title"], "expected_source": source,
        "expected_chunks": chunks, "expected_passage": passage,
    }


def main() -> int:
    labels = [f"source_class:{value}" for value in SOURCE_CLASSES]
    labels += ["feature:structured_table", "feature:historical_guidance", "feature:long_section"]
    best: dict[str, tuple[str, Path, dict, dict]] = {}
    used: set[str] = set()
    for manifest_path in MANIFESTS:
        manifest = json.loads(manifest_path.read_text())
        root = Path(manifest["source_root"])
        with gzip.open(manifest["inventory_path"], "rt", encoding="utf-8") as handle:
            for line in handle:
                entry = json.loads(line)
                document = normalize_document(json.loads(
                    (root / entry["relative_path"]).read_text()
                ))
                if not document.get("sections"):
                    continue
                for label in set(labels) & set(_selectors(document)):
                    if label == "source_class:court_decision" and manifest_path != COURT_MANIFEST:
                        continue
                    score = _rank(label, document["document_id"])
                    if label not in best or score < best[label][0]:
                        best[label] = score, manifest_path, entry, document
    fixtures = []
    for label in labels:
        _, manifest_path, entry, document = best[label]
        if label.startswith("feature:") and document["document_id"] in used:
            raise RuntimeError(f"feature fixture duplicates source-class fixture: {label}")
        fixtures.append(_snapshot(label, manifest_path, entry, document))
        used.add(document["document_id"])
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text("".join(json.dumps(item, ensure_ascii=False) + "\n" for item in fixtures))
    print(f"wrote {len(fixtures)} golden fixtures to {OUTPUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
