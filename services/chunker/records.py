"""Normalized catalog, parent and child record builders."""

import hashlib
import json
from typing import Any, Sequence

from .metadata import inherited_chunk_metadata
from .settings import CHUNKER_VERSION, TOKENIZER_VERSION
from .text import normalize_identity_text, token_count


def stable_hash(*parts: str) -> str:
    return hashlib.sha256("\x1f".join(parts).encode()).hexdigest()


def common_metadata(document: dict[str, Any]) -> dict[str, Any]:
    return {
        "document_id": document["document_id"],
        "version_id": (document.get("version") or {}).get("version_id"),
        "title": document.get("title"), "source_url": document.get("source_url"),
        "publisher": document.get("publisher"),
        "canonical_reference_id": document.get("canonical_reference_id"),
        "classification": document.get("classification") or {},
        "dates": document.get("dates") or {},
        "statute_version": document.get("statute_version"),
    }


def catalog_record(document: dict[str, Any]) -> dict[str, Any]:
    return {"schema_version": "fintax-document-catalog-1.0",
            **common_metadata(document), "references": document.get("references") or []}


def contextual_header(document: dict[str, Any], path: Sequence[str]) -> str:
    classification = document.get("classification") or {}
    version = document.get("version") or {}
    periods = ", ".join(classification.get("applicable_periods") or []) or "not specified"
    heading = " > ".join(str(item) for item in path if item) or document.get("title", "")
    lines = ["[JURISDICTION: Commonwealth of Australia]",
             f"[SOURCE: {document.get('publisher') or 'Unknown'}]",
             f"[DOCUMENT: {document.get('title') or 'Untitled'}]",
             f"[VERSION: {version.get('version_id') or 'unknown'}]",
             f"[APPLICABLE-PERIOD: {periods}]", f"[PATH: {heading}]",
             f"[AUTHORITY: {classification.get('source_class') or 'unknown'}]"]
    if document.get("canonical_reference_id"):
        lines.append(f"[CITATION: {document['canonical_reference_id']}]")
    return "\n".join(lines)


def make_parent(document, *, kind, locator, heading_path, text, parent_index):
    document_id = str(document["document_id"])
    version_id = str((document.get("version") or {}).get("version_id") or "")
    locator_key = json.dumps(locator, sort_keys=True, separators=(",", ":"))
    parent_id = stable_hash(document_id, version_id, "parent", locator_key,
                            normalize_identity_text(text), CHUNKER_VERSION)
    return {
        "schema_version": "fintax-parent-1.0", "parent_id": parent_id,
        "document_id": document_id, "version_id": version_id,
        "parent_index": parent_index, "block_type": kind,
        "heading_path": heading_path, "locator": locator, "content": text,
        "token_count": token_count(text), "tokenizer": TOKENIZER_VERSION,
        "chunker_version": CHUNKER_VERSION,
    }


def make_child(document, parent, *, child_index, text, locator):
    document_id = str(document["document_id"])
    version_id = str((document.get("version") or {}).get("version_id") or "")
    locator_key = json.dumps(locator, sort_keys=True, separators=(",", ":"))
    chunk_hash = stable_hash(document_id, version_id, locator_key,
                             normalize_identity_text(text), CHUNKER_VERSION)
    header = contextual_header(document, parent["heading_path"])
    embedding_text = f"{header}\n\n{text}"
    narrative = parent["block_type"] == "narrative"
    locator_keys = ("section_id", "char_start", "char_end", "locator_precision") if narrative else (
        "section_id", "table_id", "page_number", "row_start", "row_end", "locator_precision")
    source_locator = {key: locator.get(key) for key in locator_keys}
    return {
        "schema_version": "fintax-chunk-1.1", "chunk_id": chunk_hash,
        "chunk_hash": chunk_hash, "parent_chunk_id": parent["parent_id"],
        "document_id": document_id, "version_id": version_id,
        **inherited_chunk_metadata(document),
        "chunk_index": child_index, "chunk_type": "text" if narrative else "table",
        "heading_path": parent["heading_path"],
        "source_locator": source_locator,
        "parent_part": locator.get("parent_part"),
        "child_part": locator.get("child_part"),
        "contextual_header": header, "text": text,
        "content_for_embedding": embedding_text, "token_count": token_count(text),
        "embedding_input_token_count": token_count(embedding_text),
        "tokenizer": TOKENIZER_VERSION, "chunker_version": CHUNKER_VERSION,
        "is_active": True,
    }
