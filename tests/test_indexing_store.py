"""Tests for transactional PostgreSQL storage and vector freshness."""

from uuid import uuid4

from services.embedding.inputs import ChunkEmbeddingInput
from services.indexing.store import RetrievalStore


def _sample_input(chunk_id: str, content: str, input_sha: str = "hash1") -> ChunkEmbeddingInput:
    return ChunkEmbeddingInput(
        chunk_id=chunk_id,
        chunk_hash=chunk_id,
        parent_chunk_id="parent_1",
        document_id="doc_1",
        version_id="v1",
        source_class="court_decision",
        canonical_reference_id="[2025] HCA 1",
        authority_rank=10,
        page_status="current",
        applicable_periods=("2025",),
        source_locator={"paragraph_start": 1},
        contextual_header="[DOC]",
        text="text",
        content=content,
        input_sha256=input_sha,
    )


class MockCursor:
    def __init__(self):
        self.executed = []

    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass

    def executemany(self, sql, rows):
        self.executed.append(("executemany", sql, rows))

    def execute(self, sql, params=None):
        self.executed.append(("execute", sql, params))


class MockConnection:
    def __init__(self, fetch_result=None):
        self.executed = []
        self.committed = False
        self.cursor_obj = MockCursor()
        self.fetch_result = fetch_result or []

    def cursor(self):
        return self.cursor_obj

    def execute(self, sql, params=None):
        self.executed.append((sql, params))
        result = self.fetch_result

        class Result:
            @staticmethod
            def fetchall():
                return result

            @staticmethod
            def fetchone():
                return result[0] if result else None
        return Result()

    def commit(self):
        self.committed = True


def test_upsert_chunks_updates_all_derived_columns():
    conn = MockConnection()
    store = RetrievalStore(conn)
    item = _sample_input("c" * 64, "content")
    store.upsert_chunks((item,))
    sql = conn.cursor_obj.executed[0][1]
    assert "parent_chunk_id = EXCLUDED.parent_chunk_id" in sql
    assert "source_class = EXCLUDED.source_class" in sql
    assert "content_for_embedding = EXCLUDED.content_for_embedding" in sql
    assert "embedding_input_sha256 = EXCLUDED.embedding_input_sha256" in sql


def test_missing_detects_hash_mismatch_for_reembedding():
    chunk_id = "c" * 64
    conn = MockConnection(fetch_result=[(chunk_id, "old_hash")])
    store = RetrievalStore(conn)
    item_old = _sample_input(chunk_id, "old", "old_hash")
    item_new = _sample_input(chunk_id, "new", "new_hash")
    missing = store.missing((item_old, item_new), "profile-1")
    assert missing == (item_new,)


def test_commit_embeddings_updates_on_differing_input_hash():
    conn = MockConnection()
    store = RetrievalStore(conn)
    item = _sample_input("c" * 64, "content", "new_hash")
    run_id = uuid4()
    store.commit_embeddings(run_id, "profile-1", (item,), [[0.1] * 768], 5)
    sql = conn.cursor_obj.executed[0][1]
    assert "ON CONFLICT (chunk_id, profile_id) DO UPDATE SET" in sql
    assert "WHERE chunk_embeddings.input_sha256 <> EXCLUDED.input_sha256" in sql
    assert conn.committed is True
