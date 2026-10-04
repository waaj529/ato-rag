"""Transactional PostgreSQL storage for Phase 3 chunks and embeddings."""

import json
from uuid import UUID, uuid4

import psycopg

from services.embedding.inputs import ChunkEmbeddingInput
from services.embedding.profile import EmbeddingProfile


class RetrievalStore:
    def __init__(self, connection: psycopg.Connection) -> None:
        self.connection = connection

    def ensure_profile(self, profile: EmbeddingProfile) -> None:
        self.connection.execute(
            """INSERT INTO embedding_profiles
               (profile_id, provider, model, dimensions, document_task, query_task,
                normalization, status)
               VALUES (%s,%s,%s,%s,%s,%s,%s,%s)
               ON CONFLICT (profile_id) DO UPDATE SET
                 normalization = EXCLUDED.normalization, status = EXCLUDED.status""",
            (profile.profile_id, profile.provider, profile.model, profile.dimensions,
             profile.document_task, profile.query_task, profile.normalization, profile.status),
        )
        self.connection.commit()

    def start_run(self, profile_id: str, corpus_revision: str) -> UUID:
        run_id = uuid4()
        self.connection.execute(
            "INSERT INTO embedding_runs (run_id, profile_id, corpus_revision, status) "
            "VALUES (%s,%s,%s,'running')", (run_id, profile_id, corpus_revision),
        )
        self.connection.commit()
        return run_id

    def total_input_tokens(self, profile_id: str, corpus_revision: str) -> int:
        row = self.connection.execute(
            "SELECT coalesce(sum(input_tokens), 0) FROM embedding_runs "
            "WHERE profile_id=%s AND corpus_revision=%s",
            (profile_id, corpus_revision),
        ).fetchone()
        return int(row[0])

    def upsert_chunks(self, batch: tuple[ChunkEmbeddingInput, ...]) -> None:
        rows = [(
            item.chunk_id, item.chunk_hash, item.parent_chunk_id, item.document_id,
            item.version_id, item.source_class, item.canonical_reference_id,
            item.authority_rank, item.page_status, json.dumps(item.applicable_periods),
            json.dumps(item.source_locator, sort_keys=True), item.contextual_header,
            item.text, item.content, item.input_sha256,
        ) for item in batch]
        with self.connection.cursor() as cursor:
            cursor.executemany(
                """INSERT INTO retrieval_chunks
                   (chunk_id, chunk_hash, parent_chunk_id, document_id, version_id,
                    source_class, canonical_reference_id, authority_rank, page_status,
                    applicable_periods, source_locator, contextual_header, content,
                    content_for_embedding, embedding_input_sha256)
                   VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s::jsonb,%s::jsonb,%s,%s,%s,%s)
                   ON CONFLICT (chunk_id) DO UPDATE SET
                     is_active = true,
                     parent_chunk_id = EXCLUDED.parent_chunk_id,
                     source_class = EXCLUDED.source_class,
                     canonical_reference_id = EXCLUDED.canonical_reference_id,
                     authority_rank = EXCLUDED.authority_rank,
                     page_status = EXCLUDED.page_status,
                     applicable_periods = EXCLUDED.applicable_periods,
                     source_locator = EXCLUDED.source_locator,
                     contextual_header = EXCLUDED.contextual_header,
                     content = EXCLUDED.content,
                     content_for_embedding = EXCLUDED.content_for_embedding,
                     embedding_input_sha256 = EXCLUDED.embedding_input_sha256""", rows,
            )

    def missing(self, batch: tuple[ChunkEmbeddingInput, ...], profile_id: str) -> tuple[ChunkEmbeddingInput, ...]:
        rows = self.connection.execute(
            "SELECT chunk_id, input_sha256 FROM chunk_embeddings "
            "WHERE profile_id=%s AND chunk_id=ANY(%s)",
            (profile_id, [item.chunk_id for item in batch]),
        ).fetchall()
        present = {(str(row[0]).strip(), str(row[1]).strip()) for row in rows}
        return tuple(item for item in batch
                     if (item.chunk_id, item.input_sha256) not in present)

    def commit_embeddings(self, run_id: UUID, profile_id: str,
                          batch: tuple[ChunkEmbeddingInput, ...], vectors,
                          input_tokens: int) -> None:
        rows = [(item.chunk_id, profile_id, _vector_text(vector), item.input_sha256)
                for item, vector in zip(batch, vectors, strict=True)]
        with self.connection.cursor() as cursor:
            cursor.executemany(
                """INSERT INTO chunk_embeddings (chunk_id, profile_id, embedding, input_sha256)
                   VALUES (%s,%s,%s::vector,%s)
                   ON CONFLICT (chunk_id, profile_id) DO UPDATE SET
                     embedding = EXCLUDED.embedding,
                     input_sha256 = EXCLUDED.input_sha256,
                     created_at = now()
                   WHERE chunk_embeddings.input_sha256 <> EXCLUDED.input_sha256""", rows,
            )
            cursor.execute(
                """UPDATE embedding_runs SET embedded_count=embedded_count+%s,
                   input_count=input_count+%s, input_tokens=input_tokens+%s WHERE run_id=%s""",
                (len(batch), len(batch), input_tokens, run_id),
            )
        self.connection.commit()

    def finish(self, run_id: UUID, status: str) -> None:
        self.connection.execute(
            "UPDATE embedding_runs SET status=%s, completed_at=now() WHERE run_id=%s",
            (status, run_id),
        )
        self.connection.commit()


def _vector_text(vector) -> str:
    return "[" + ",".join(format(value, ".9g") for value in vector) + "]"
