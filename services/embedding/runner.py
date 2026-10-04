"""Resumable orchestration from verified chunk inputs to PostgreSQL vectors."""

from collections.abc import Callable, Iterable

from services.indexing.store import RetrievalStore

from .client import IsaacusEmbeddingClient
from .inputs import ChunkEmbeddingInput, iter_batches


Progress = Callable[[int, int, int], None]


def run_embeddings(inputs: Iterable[ChunkEmbeddingInput], client: IsaacusEmbeddingClient,
                   store: RetrievalStore, corpus_revision: str, batch_size: int = 128,
                   max_batches: int | None = None, progress: Progress | None = None,
                   max_corpus_tokens: int | None = None) -> dict:
    profile = client.profile
    store.ensure_profile(profile)
    corpus_tokens = store.total_input_tokens(profile.profile_id, corpus_revision)
    run_id = store.start_run(profile.profile_id, corpus_revision)
    embedded = tokens = processed_batches = 0
    status = "complete"
    try:
        for batch in iter_batches(inputs, batch_size):
            if max_batches is not None and processed_batches >= max_batches:
                break
            store.upsert_chunks(batch)
            missing = store.missing(batch, profile.profile_id)
            if missing:
                if max_corpus_tokens is not None and corpus_tokens >= max_corpus_tokens:
                    store.connection.rollback()
                    status = "budget_stopped"
                    break
                result = client.embed_documents([item.content for item in missing])
                store.commit_embeddings(run_id, profile.profile_id, missing,
                                        result.vectors, result.input_tokens)
                embedded += len(missing)
                tokens += result.input_tokens
                corpus_tokens += result.input_tokens
            else:
                store.connection.commit()
            processed_batches += 1
            if progress:
                progress(processed_batches, embedded, tokens)
        store.finish(run_id, status)
    except BaseException:
        try:
            store.connection.rollback()
        except BaseException:
            pass
        try:
            store.finish(run_id, "failed")
        except BaseException:
            pass
        raise
    return {"run_id": str(run_id), "status": status, "batches": processed_batches,
            "embedded": embedded, "input_tokens": tokens,
            "corpus_input_tokens": corpus_tokens}
