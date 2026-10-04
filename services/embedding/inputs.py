"""Deterministic Phase 3 inputs read from verified child-chunk exports."""

from dataclasses import dataclass
import gzip
import hashlib
import json
from pathlib import Path
from typing import Iterable, Iterator


@dataclass(frozen=True)
class ChunkEmbeddingInput:
    chunk_id: str
    chunk_hash: str
    parent_chunk_id: str
    document_id: str
    version_id: str
    source_class: str
    canonical_reference_id: str | None
    authority_rank: int | None
    page_status: str | None
    applicable_periods: tuple[str, ...]
    source_locator: dict
    contextual_header: str
    text: str
    content: str
    input_sha256: str


def iter_chunk_inputs(chunk_roots: Iterable[Path]) -> Iterator[ChunkEmbeddingInput]:
    seen: set[str] = set()
    for root in chunk_roots:
        report = json.loads((root / "verification_report.json").read_text())
        if report.get("valid") is not True:
            raise ValueError(f"chunk export is not verified: {root}")
        for path in sorted((root / "children").glob("*.jsonl.gz")):
            with gzip.open(path, "rt", encoding="utf-8") as handle:
                for line in handle:
                    record = json.loads(line)
                    if record.get("is_active") is not True:
                        continue
                    yield _input(record, seen)


def _input(record: dict, seen: set[str]) -> ChunkEmbeddingInput:
    chunk_id = record.get("chunk_id")
    chunk_hash = record.get("chunk_hash")
    content = record.get("content_for_embedding")
    if not isinstance(chunk_id, str) or len(chunk_id) != 64:
        raise ValueError("invalid chunk_id in embedding input")
    if chunk_id in seen:
        raise ValueError(f"duplicate embedding input: {chunk_id}")
    if chunk_hash != chunk_id:
        raise ValueError(f"chunk hash mismatch: {chunk_id}")
    if not isinstance(content, str) or not content.strip():
        raise ValueError(f"missing embedding content: {chunk_id}")
    seen.add(chunk_id)
    return ChunkEmbeddingInput(
        chunk_id=chunk_id,
        chunk_hash=chunk_hash,
        parent_chunk_id=str(record["parent_chunk_id"]),
        document_id=str(record["document_id"]),
        version_id=str(record["version_id"]),
        source_class=str(record["source_class"]),
        canonical_reference_id=record.get("canonical_reference_id"),
        authority_rank=record.get("authority_rank"),
        page_status=record.get("page_status"),
        applicable_periods=tuple(str(value) for value in record.get("applicable_periods", [])),
        source_locator=record["source_locator"],
        contextual_header=str(record["contextual_header"]),
        text=str(record["text"]),
        content=content,
        input_sha256=hashlib.sha256(content.encode()).hexdigest(),
    )


def iter_batches(inputs: Iterable[ChunkEmbeddingInput], size: int = 128) -> Iterator[tuple[ChunkEmbeddingInput, ...]]:
    if not 1 <= size <= 128:
        raise ValueError("embedding batch size must be between 1 and 128")
    batch: list[ChunkEmbeddingInput] = []
    for item in inputs:
        batch.append(item)
        if len(batch) == size:
            yield tuple(batch)
            batch.clear()
    if batch:
        yield tuple(batch)
