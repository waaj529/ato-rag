CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE embedding_profiles (
    profile_id text PRIMARY KEY,
    provider text NOT NULL,
    model text NOT NULL,
    model_revision text,
    dimensions integer NOT NULL CHECK (dimensions = 768),
    document_task text NOT NULL CHECK (document_task = 'retrieval/document'),
    query_task text NOT NULL CHECK (query_task = 'retrieval/query'),
    normalization text NOT NULL,
    status text NOT NULL CHECK (status IN ('provisional', 'active', 'retired')),
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE retrieval_chunks (
    chunk_id char(64) PRIMARY KEY,
    chunk_hash char(64) NOT NULL,
    parent_chunk_id char(64) NOT NULL,
    document_id text NOT NULL,
    version_id text NOT NULL,
    source_class text NOT NULL,
    canonical_reference_id text,
    authority_rank integer,
    page_status text,
    applicable_periods jsonb NOT NULL DEFAULT '[]'::jsonb,
    source_locator jsonb NOT NULL,
    contextual_header text NOT NULL,
    content text NOT NULL,
    content_for_embedding text NOT NULL,
    embedding_input_sha256 char(64) NOT NULL,
    is_active boolean NOT NULL DEFAULT true,
    search_vector tsvector GENERATED ALWAYS AS (
        to_tsvector('english', coalesce(canonical_reference_id, '') || ' ' || content)
    ) STORED,
    UNIQUE (chunk_id, version_id)
);

CREATE INDEX retrieval_chunks_fts_idx ON retrieval_chunks USING gin (search_vector);
CREATE INDEX retrieval_chunks_document_idx ON retrieval_chunks (document_id, version_id);
CREATE INDEX retrieval_chunks_reference_idx ON retrieval_chunks (canonical_reference_id)
    WHERE canonical_reference_id IS NOT NULL;

CREATE TABLE exact_identifiers (
    normalized_identifier text NOT NULL,
    identifier_type text NOT NULL,
    chunk_id char(64) NOT NULL REFERENCES retrieval_chunks(chunk_id) ON DELETE CASCADE,
    PRIMARY KEY (normalized_identifier, identifier_type, chunk_id)
);

CREATE INDEX exact_identifiers_lookup_idx
    ON exact_identifiers (normalized_identifier, identifier_type);

CREATE TABLE chunk_embeddings (
    chunk_id char(64) NOT NULL REFERENCES retrieval_chunks(chunk_id) ON DELETE CASCADE,
    profile_id text NOT NULL REFERENCES embedding_profiles(profile_id),
    embedding vector(768) NOT NULL,
    input_sha256 char(64) NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (chunk_id, profile_id)
);

CREATE TABLE embedding_runs (
    run_id uuid PRIMARY KEY,
    profile_id text NOT NULL REFERENCES embedding_profiles(profile_id),
    corpus_revision text NOT NULL,
    status text NOT NULL CHECK (status IN ('running', 'complete', 'failed', 'budget_stopped')),
    input_count bigint NOT NULL DEFAULT 0,
    embedded_count bigint NOT NULL DEFAULT 0,
    input_tokens bigint NOT NULL DEFAULT 0,
    started_at timestamptz NOT NULL DEFAULT now(),
    completed_at timestamptz
);

CREATE TABLE index_publications (
    publication_id uuid PRIMARY KEY,
    profile_id text NOT NULL REFERENCES embedding_profiles(profile_id),
    embedding_run_id uuid NOT NULL REFERENCES embedding_runs(run_id),
    status text NOT NULL CHECK (status IN ('staging', 'active', 'retired')),
    published_at timestamptz
);

CREATE UNIQUE INDEX index_publications_one_active_idx
    ON index_publications (profile_id) WHERE status = 'active';
