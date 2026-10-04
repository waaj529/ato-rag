-- Rebuild lexical evidence over the same deterministic context supplied to embeddings.
-- Run outside a transaction because the GIN index operations are concurrent.
DROP INDEX CONCURRENTLY IF EXISTS retrieval_chunks_fts_idx;

ALTER TABLE retrieval_chunks DROP COLUMN search_vector;
ALTER TABLE retrieval_chunks ADD COLUMN search_vector tsvector GENERATED ALWAYS AS (
    to_tsvector(
        'english',
        coalesce(canonical_reference_id, '') || ' ' || contextual_header || ' ' || content
    )
) STORED;

CREATE INDEX CONCURRENTLY retrieval_chunks_fts_idx
    ON retrieval_chunks USING gin (search_vector);

ANALYZE retrieval_chunks;
