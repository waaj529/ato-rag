# Migrations

PostgreSQL and pgvector migrations begin in Phase 3. Generated chunk JSONL is
not a database migration.

`0001_phase3_retrieval.sql` creates the 768-dimensional Kanon profile schema,
canonical retrieval rows, exact-identifier mappings, PostgreSQL FTS, embedding-run audit
records and atomic index-publication records. Apply it only to PostgreSQL with `vector`.

Load the initial vectors before applying `0002_phase3_hnsw.sql`; pgvector documents that
bulk loading before HNSW construction is faster. The second migration uses `CONCURRENTLY`
and must run outside a transaction.

`0003_index_publication_uniqueness.sql` adds the partial unique index that permits
only one active publication per embedding profile. It also runs outside a transaction.

`0004_phase3_lexical_context.sql` rebuilds the stored PostgreSQL FTS vector over the
canonical citation, deterministic legal context header/path and source content. Its GIN
drop/create operations use `CONCURRENTLY`, so apply the file outside a transaction.
