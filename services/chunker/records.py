"""Canonical record factories for parent and child chunks."""

import json

from .metadata import contextual_header, inherited_chunk_metadata
from .settings import CHUNKER_VERSION, TOKENIZER_VERSION
from .text import normalize_identity_text, token_count
from packages.security import stable_hash


def make_catalog_record(document: dict) -> dict:
    classification = document.get("classification") or {}
    version = document.get("version") or {}
    document_id = str(document["document_id"])
    version_id = str(version.get("version_id") or "")
    catalog_hash = stable_hash(document_id, version_id, "catalog", CHUNKER_VERSION)
    return {
        "schema_version": "fintax-catalog-1.1",
        "catalog_id": catalog_hash,
        "document_id": document_id,
        "version_id": version_id,
        "source_url": document["source_url"],
        "publisher": document["publisher"],
        "title": document["title"],
        "corpus": classification.get("corpus"),
        "source_class": classification.get("source_class"),
        "applicable_periods": classification.get("applicable_periods", []),
        "historical_guidance": classification.get("historical_guidance", False),
        "binding_effect": classification.get("binding_effect", "none"),
        "authority_rank": classification.get("authority_rank", 100),
        "content_sha256": version.get("content_sha256", ""),
        "source_locator": document.get("source_locator") or {},
        "canonical_reference_id": document.get("canonical_reference_id"),
        "canonical_reference": document.get("canonical_reference"),
        "classification": classification,
        "dates": document.get("dates") or {},
        "statute_version": document.get("statute_version"),
        "references": document.get("references") or [],
        "chunker_version": CHUNKER_VERSION,
    }


catalog_record = make_catalog_record


def make_parent(document, *, kind, locator, heading_path, text, parent_index):
    document_id = str(document["document_id"])
    version_id = str((document.get("version") or {}).get("version_id") or "")
    locator_key = json.dumps(locator, sort_keys=True, separators=(",", ":"))
    parent_id = stable_hash(document_id, version_id, "parent", locator_key,
                            normalize_identity_text(text), CHUNKER_VERSION)
    sizing = {"method": TOKENIZER_VERSION, "text_units": token_count(text)}
    return {
        "schema_version": "fintax-parent-1.1", "parent_id": parent_id,
        "document_id": document_id, "version_id": version_id,
        "parent_index": parent_index, "block_type": kind,
        "heading_path": heading_path, "locator": locator, "content": text,
        "sizing": sizing,
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
    sizing = {"method": TOKENIZER_VERSION, "text_units": token_count(text),
              "embedding_input_units": token_count(embedding_text)}
    return {
        "schema_version": "fintax-chunk-1.2", "chunk_id": chunk_hash,
        "chunk_hash": chunk_hash, "parent_chunk_id": parent["parent_id"],
        "document_id": document_id, "version_id": version_id,
        **inherited_chunk_metadata(document),
        "chunk_index": child_index, "chunk_type": "text" if narrative else "table",
        "heading_path": parent["heading_path"],
        "source_locator": source_locator,
        "parent_part": locator.get("parent_part"),
        "child_part": locator.get("child_part"),
        "contextual_header": header, "text": text,
        "content_for_embedding": embedding_text,
        "sizing": sizing,
        "chunker_version": CHUNKER_VERSION,
        "is_active": True,
    }


def sizing_units(record: dict) -> int:
    """Convenience accessor for the unit count of a sizing dictionary."""
    return int(record["sizing"]["text_units"])
