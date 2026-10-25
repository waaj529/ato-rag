#!/usr/bin/env sh
# ==============================================================================
# Finalize roles and grants for FinTaxGPT API service connection
# Runs automatically inside postgres container after 001-data.sql.gz initialization
# ==============================================================================
set -e

APP_PASSWORD="${FINTAX_POSTGRES_PASSWORD:-fintaxgpt-local-only}"

psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" <<-EOSQL
    DO \$\$ BEGIN
        IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'fintax_api') THEN
            CREATE ROLE fintax_api LOGIN NOSUPERUSER NOBYPASSRLS NOCREATEDB NOCREATEROLE NOINHERIT;
        END IF;
    END \$\$;
    ALTER ROLE fintax_api WITH PASSWORD '$APP_PASSWORD';
    GRANT USAGE ON SCHEMA public TO fintax_api;
    GRANT SELECT ON ALL TABLES IN SCHEMA public TO fintax_api;
    ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT ON TABLES TO fintax_api;
EOSQL
