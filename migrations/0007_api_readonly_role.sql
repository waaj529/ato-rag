-- Deployment-only role: no change to corpus, indexes, retrieval or existing roles.
-- Set the login credential using the deployment secret manager, not this migration.
DO $$ BEGIN
    IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'fintax_api') THEN
        CREATE ROLE fintax_api LOGIN NOSUPERUSER NOBYPASSRLS NOCREATEDB NOCREATEROLE NOINHERIT;
    END IF;
END $$;
GRANT USAGE ON SCHEMA public TO fintax_api;
GRANT SELECT ON retrieval_chunks, chunk_embeddings, exact_identifiers,
                retrieval_parents, customer_matters TO fintax_api;
