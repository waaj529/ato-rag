"""Atomic compressed shard writer for chunking output."""

from collections import Counter
import gzip
import json
from pathlib import Path
import shutil

from .core import catalog_record, chunk_document
from .settings import ChunkerConfig


def compact(record: dict) -> str:
    return json.dumps(record, ensure_ascii=False, separators=(",", ":")) + "\n"


class ChunkShardWriter:
    def __init__(self, output: Path, config: ChunkerConfig):
        self.output, self.config = output, config
        self.staging = output.with_name(output.name + ".staging")
        if self.staging.exists():
            shutil.rmtree(self.staging)
        for name in ("parents", "children", "catalog"):
            (self.staging / name).mkdir(parents=True)
        self.handles = {name: {} for name in ("parents", "children", "catalog")}
        self.parent_ids, self.child_ids = set(), set()
        self.counts = Counter()

    def _handle(self, kind: str, shard: str):
        if shard not in self.handles[kind]:
            path = self.staging / kind / f"{shard}.jsonl.gz"
            self.handles[kind][shard] = gzip.open(path, "wt", encoding="utf-8")
        return self.handles[kind][shard]

    def write_document(self, document: dict, shard: str) -> None:
        parents, children = chunk_document(document, self.config)
        self._handle("catalog", shard).write(compact(catalog_record(document)))
        self.counts["catalog_documents"] += 1
        for parent in parents:
            if parent["parent_id"] in self.parent_ids:
                raise RuntimeError(f"duplicate parent id: {parent['parent_id']}")
            self.parent_ids.add(parent["parent_id"])
            self._handle("parents", shard).write(compact(parent))
            self.counts["parents"] += 1
            self.counts[f"parent_{parent['block_type']}"] += 1
        for child in children:
            if child["chunk_id"] in self.child_ids:
                raise RuntimeError(f"duplicate chunk id: {child['chunk_id']}")
            if child["token_count"] > self.config.child_hard_max_tokens:
                raise RuntimeError(f"oversized chunk: {child['chunk_id']}")
            self.child_ids.add(child["chunk_id"])
            self._handle("children", shard).write(compact(child))
            self.counts["children"] += 1
            self.counts[f"child_{child['chunk_type']}"] += 1
        self.counts["documents"] += 1
        if not children:
            self.counts["documents_without_chunks"] += 1

    def close(self) -> None:
        for group in self.handles.values():
            for handle in group.values():
                handle.close()

    def publish(self, report: dict) -> None:
        (self.staging / "chunking_report.json").write_text(
            json.dumps(report, indent=2, sort_keys=True) + "\n"
        )
        if self.output.exists():
            shutil.rmtree(self.output)
        self.staging.rename(self.output)

    @property
    def shard_count(self) -> int:
        return len(self.handles["children"])
