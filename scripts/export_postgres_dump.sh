#!/usr/bin/env bash
# ==============================================================================
# Export FinTaxGPT PostgreSQL Corpus & Embeddings Dump
# ==============================================================================
set -euo pipefail

OUTPUT_PATH="${1:-fintax-rag-local/postgres-data.sql.gz}"
PG_HOST="${PG_HOST:-127.0.0.1}"
PG_PORT="${PG_PORT:-5433}"
PG_USER="${PG_USER:-fintaxgpt}"
PG_DB="${PG_DB:-fintaxgpt}"
PG_PASSWORD="${PG_PASSWORD:-fintaxgpt-local-only}"

mkdir -p "$(dirname "$OUTPUT_PATH")"

echo "==> Exporting FinTaxGPT PostgreSQL database to: $OUTPUT_PATH"
if command -v pg_dump >/dev/null 2>&1; then
    PGPASSWORD="$PG_PASSWORD" pg_dump \
        -h "$PG_HOST" \
        -p "$PG_PORT" \
        -U "$PG_USER" \
        -d "$PG_DB" \
        --clean \
        --if-exists \
        --no-owner \
        --no-privileges | gzip > "$OUTPUT_PATH"
elif docker ps --format '{{.Names}}' | grep -q "postgres"; then
    CONTAINER_NAME=$(docker ps --format '{{.Names}}' | grep "postgres" | head -n 1)
    echo "==> Using Docker container '$CONTAINER_NAME' for pg_dump..."
    docker exec "$CONTAINER_NAME" pg_dump \
        -U "$PG_USER" \
        -d "$PG_DB" \
        --clean \
        --if-exists \
        --no-owner \
        --no-privileges | gzip > "$OUTPUT_PATH"
else
    echo "ERROR: Neither local 'pg_dump' nor a running Docker PostgreSQL container was found." >&2
    echo "Ensure PostgreSQL (with pgvector) is running on port $PG_PORT or inside Docker." >&2
    exit 1
fi

FILE_SIZE=$(du -h "$OUTPUT_PATH" | cut -f1)
echo "==> Export complete: $OUTPUT_PATH ($FILE_SIZE)"
echo "==> Ready to package into fintax-rag-local bundle."
