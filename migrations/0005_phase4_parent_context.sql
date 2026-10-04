-- Phase 4 parent expansion store. Phase 3 retrieval tables remain unchanged.

CREATE TABLE IF NOT EXISTS retrieval_parents (
    parent_id char(64) PRIMARY KEY,
    document_id text NOT NULL,
    version_id text NOT NULL,
    source_class text NOT NULL,
    canonical_reference_id text,
    authority_rank integer,
    title text NOT NULL,
    source_url text NOT NULL,
    block_type text NOT NULL,
    heading_path jsonb NOT NULL DEFAULT '[]'::jsonb,
    source_locator jsonb NOT NULL,
    content text NOT NULL,
    text_units integer NOT NULL CHECK (text_units >= 0),
    chunker_version text NOT NULL,
    is_active boolean NOT NULL DEFAULT true,
    UNIQUE (parent_id, version_id)
);

CREATE INDEX IF NOT EXISTS retrieval_parents_document_idx
    ON retrieval_parents (document_id, version_id);
