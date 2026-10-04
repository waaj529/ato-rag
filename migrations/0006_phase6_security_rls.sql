-- Phase 6: Customer matter isolation with PostgreSQL Row-Level Security (RLS) and Dead-Letter Queue (DLQ)

DO $$
BEGIN
    IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'fintax_app') THEN
        CREATE ROLE fintax_app NOBYPASSRLS;
    END IF;
END $$;

CREATE TABLE IF NOT EXISTS customer_matters (
    matter_id TEXT PRIMARY KEY,
    tenant_id TEXT NOT NULL,
    name TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS matter_documents (
    doc_id TEXT PRIMARY KEY,
    matter_id TEXT NOT NULL REFERENCES customer_matters(matter_id) ON DELETE CASCADE,
    tenant_id TEXT NOT NULL,
    title TEXT NOT NULL,
    content TEXT NOT NULL,
    classification TEXT NOT NULL DEFAULT 'CUSTOMER_CONFIDENTIAL',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Dead Letter Queue for durable asynchronous job failures
CREATE TABLE IF NOT EXISTS dead_letter_queue (
    job_id TEXT PRIMARY KEY,
    task_name TEXT NOT NULL,
    payload JSONB NOT NULL,
    error_message TEXT NOT NULL,
    retry_count INT NOT NULL DEFAULT 0,
    status TEXT NOT NULL DEFAULT 'FAILED',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_matters_tenant ON customer_matters(tenant_id);
CREATE INDEX IF NOT EXISTS idx_matter_docs_tenant ON matter_documents(tenant_id, matter_id);
CREATE INDEX IF NOT EXISTS idx_dlq_status ON dead_letter_queue(status, created_at);

GRANT ALL ON ALL TABLES IN SCHEMA public TO fintax_app;

-- Enable Row Level Security (RLS)
ALTER TABLE customer_matters ENABLE ROW LEVEL SECURITY;
ALTER TABLE matter_documents ENABLE ROW LEVEL SECURITY;

-- Force RLS even for table owners to avoid accidental bypass in application queries
ALTER TABLE customer_matters FORCE ROW LEVEL SECURITY;
ALTER TABLE matter_documents FORCE ROW LEVEL SECURITY;

-- Create fail-closed policies based on session variable app.current_tenant_id
DROP POLICY IF EXISTS tenant_isolation_matters ON customer_matters;
CREATE POLICY tenant_isolation_matters ON customer_matters
    FOR ALL
    USING (tenant_id = NULLIF(current_setting('app.current_tenant_id', true), ''))
    WITH CHECK (tenant_id = NULLIF(current_setting('app.current_tenant_id', true), ''));

DROP POLICY IF EXISTS tenant_isolation_documents ON matter_documents;
CREATE POLICY tenant_isolation_documents ON matter_documents
    FOR ALL
    USING (tenant_id = NULLIF(current_setting('app.current_tenant_id', true), ''))
    WITH CHECK (tenant_id = NULLIF(current_setting('app.current_tenant_id', true), ''));
