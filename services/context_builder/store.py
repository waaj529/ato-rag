"""PostgreSQL hydration and parent lookup for Phase 4."""

import json

import psycopg

from services.reranking import HydratedCandidate

from .models import ParentRecord


class Phase4Store:
    def __init__(self, connection: psycopg.Connection) -> None:
        self.connection = connection

    def hydrate(self, chunks) -> tuple[HydratedCandidate, ...]:
        by_id = {item.candidate.chunk_id: item for item in chunks}
        if not by_id:
            return ()
        rows = self.connection.execute(
            """SELECT chunk_id, parent_chunk_id, source_class, canonical_reference_id,
                      contextual_header, content, content_for_embedding
               FROM retrieval_chunks WHERE is_active AND chunk_id=ANY(%s)""",
            (list(by_id),),
        ).fetchall()
        hydrated = {str(row[0]).strip(): HydratedCandidate(
            retrieved=by_id[str(row[0]).strip()], parent_chunk_id=str(row[1]).strip(),
            source_class=str(row[2]), canonical_reference_id=row[3],
            contextual_header=str(row[4]), content=str(row[5]),
            content_for_reranking=str(row[6]),
        ) for row in rows}
        return tuple(hydrated[item.candidate.chunk_id] for item in chunks
                     if item.candidate.chunk_id in hydrated)

    def parents(self, parent_ids: tuple[str, ...]) -> dict[str, ParentRecord]:
        if not parent_ids:
            return {}
        rows = self.connection.execute(
            """SELECT parent_id, document_id, version_id, source_class,
                      canonical_reference_id, authority_rank, title, source_url,
                      heading_path, source_locator, content, text_units
               FROM retrieval_parents WHERE is_active AND parent_id=ANY(%s)""",
            (list(parent_ids),),
        ).fetchall()
        return {str(row[0]).strip(): ParentRecord(
            parent_id=str(row[0]).strip(), document_id=str(row[1]), version_id=str(row[2]),
            source_class=str(row[3]), canonical_reference_id=row[4], authority_rank=row[5],
            title=str(row[6]), source_url=str(row[7]), heading_path=tuple(_json(row[8])),
            source_locator=_json(row[9]), content=str(row[10]), text_units=int(row[11]),
        ) for row in rows}


def _json(value):
    return value if isinstance(value, (dict, list)) else json.loads(value)
