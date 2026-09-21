"""Public orchestration API for one ready-document record."""

from typing import Any

from .records import catalog_record, make_child, make_parent
from .settings import ChunkerConfig
from .spans import TextSpan, split_spans
from .strategies import SourceBlock, narrative_blocks, table_blocks
from .text import strip_markdown_tables, token_count


def _narrative_locator(block: SourceBlock, parent: TextSpan, child: TextSpan) -> dict:
    start = block.locator["segment_start"] + parent.char_start + child.char_start
    return {"section_id": block.locator.get("section_id"), "char_start": start,
            "char_end": start + len(child.text), "locator_precision": "exact"}


def _table_locator(block: SourceBlock, parent: TextSpan, child: TextSpan) -> dict:
    start = parent.char_start + child.char_start
    end = parent.char_start + child.char_end
    rows = [number for number, row_start, row_end in block.row_spans
            if row_start < end and row_end > start]
    return {"section_id": block.locator.get("section_id"),
            "table_id": block.locator.get("table_id"),
            "page_number": block.locator.get("page_number"),
            "row_start": min(rows) if rows else None,
            "row_end": max(rows) if rows else None,
            "locator_precision": "table_rows"}


def _chunk_block(document: dict, block: SourceBlock, cfg: ChunkerConfig,
                 parents: list, children: list) -> None:
    parent_spans = split_spans(block.text, target=cfg.parent_target_tokens,
                               hard_max=cfg.parent_hard_max_tokens)
    for parent_part, parent_span in enumerate(parent_spans):
        parent_locator = {**block.locator, "parent_part": parent_part}
        parent = make_parent(document, kind=block.kind, locator=parent_locator,
                             heading_path=block.heading_path, text=parent_span.text,
                             parent_index=len(parents))
        parents.append(parent)
        overlap = cfg.overlap_tokens if block.kind == "narrative" else 0
        child_spans = split_spans(parent_span.text, target=cfg.child_target_tokens,
                                  hard_max=cfg.child_hard_max_tokens, overlap=overlap)
        for child_span in child_spans:
            locator = (_narrative_locator(block, parent_span, child_span)
                       if block.kind == "narrative"
                       else _table_locator(block, parent_span, child_span))
            locator["parent_part"] = parent_part
            locator["child_part"] = len(children)
            children.append(make_child(document, parent, child_index=len(children),
                                       text=child_span.text, locator=locator))


def chunk_document(document: dict[str, Any], config: ChunkerConfig | None = None):
    cfg = config or ChunkerConfig()
    cfg.validate()
    if document.get("schema_version") != "ready-document-1.0":
        raise ValueError(f"unsupported schema: {document.get('schema_version')!r}")
    if not document.get("document_id") or not (document.get("version") or {}).get("version_id"):
        raise ValueError("document_id and version.version_id are required")
    parents, children = [], []
    blocks = [*narrative_blocks(document), *table_blocks(document)]
    for block in blocks:
        _chunk_block(document, block, cfg, parents, children)
    return parents, children


__all__ = ["ChunkerConfig", "catalog_record", "chunk_document",
           "strip_markdown_tables", "token_count"]

