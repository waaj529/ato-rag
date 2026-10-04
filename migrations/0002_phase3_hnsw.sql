-- Apply after the initial embedding load; run outside a transaction.
CREATE INDEX CONCURRENTLY chunk_embeddings_hnsw_idx ON chunk_embeddings
    USING hnsw (embedding vector_cosine_ops)
    WITH (m = 16, ef_construction = 128);
