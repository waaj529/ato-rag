# FinTaxGPT Local Deployment Bundle

This bundle contains everything needed for a developer to run the complete FinTaxGPT RAG system locally using Docker Compose, including the PostgreSQL/pgvector database with pre-embedded tax law chunks and the authenticated FastAPI application.

---

## 1. Directory Structure

```text
fintax-rag-local/
├── docker-compose.yml          # Orchestrates PostgreSQL (pgvector) and RAG API
├── .env.example                # Template for developer's local API keys and passwords
├── .gitignore                  # Prevents accidental commit of .env and .sql.gz
├── init-scripts/
│   └── 002-finalize-roles.sh   # Sets fintax_api role permissions on first start
├── postgres-data.sql.gz        # PostgreSQL dump with chunks, vectors & schema (place here)
└── README.md                   # This instruction guide
```

> **Important**: Docker images contain only application binaries. The corpus embeddings and chunks reside in the PostgreSQL database. Mounting `postgres-data.sql.gz` ensures the PostgreSQL Docker volume automatically initializes with the entire corpus on first startup.

---

## 2. Prerequisites

- [Docker Desktop](https://www.docker.com/products/docker-desktop/) (v24+ recommended)
- Docker Compose v2 (`docker compose`)
- Minimum 6 GB RAM allocated to Docker

---

## 3. Quick Start Setup

### Step 1: Configure Environment Variables

Copy `.env.example` to `.env`:

```sh
cp .env.example .env
```

Open `.env` and fill in your actual credentials:
- `ISAACUS_API_KEY`: Required for generating 1024-dimensional query embeddings for legal vector search.
- `OPENAI_API_KEY` / `FINTAX_LLM_API_KEY`: Required for answer generation.
- `FINTAX_CHAT_SERVICE_API_KEY`: Bearer token for accessing API endpoints (minimum 32 characters).
- `FINTAX_POSTGRES_PASSWORD`: Password for local PostgreSQL database (default: `fintaxgpt-local-only`).

### Step 2: Verify Database Dump

Ensure `postgres-data.sql.gz` is present in this directory:

```sh
ls -lh postgres-data.sql.gz
```

*(If generating from an existing environment, see [Database Dump Instructions](#exporting-the-database-dump-pg_dump) below).*

### Step 3: Start the Stack

Run Docker Compose from this directory:

```sh
docker compose up -d
```

Docker will:
1. Pull and start `pgvector/pgvector:0.8.6-pg17-bookworm`.
2. Automatically restore `postgres-data.sql.gz` into the database volume on first initialization.
3. Configure roles and permissions via `init-scripts/002-finalize-roles.sh`.
4. Wait for PostgreSQL to become healthy before launching the `rag` container on port `8002`.

Check container status and logs:

```sh
docker compose ps
docker compose logs -f rag
```

---

## 4. Querying the Local RAG API

### Endpoint 1: Pure Retrieval (`/v1/retrieve`)

Retrieve authoritative ATO chunks and statutory provisions without invoking the generative LLM:

```sh
curl -X POST http://127.0.0.1:8002/v1/retrieve \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer local-dev-service-key-32chars-minimum-token" \
  -d '{
    "query": "What is the statutory definition of a CGT asset under Section 108-5?"
  }'
```

### Endpoint 2: Full Grounded Answer (`/v1/answer`)

Execute end-to-end multi-channel retrieval, reranking, and verified answer synthesis:

```sh
curl -X POST http://127.0.0.1:8002/v1/answer \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer local-dev-service-key-32chars-minimum-token" \
  -d '{
    "query": "What is the statutory definition of a CGT asset under Section 108-5?"
  }'
```

---

## 5. Offline Image Transfer (Air-Gapped / Direct File Sharing)

If sharing images without pulling from Docker Hub:

### On Source Machine (Exporting):
```sh
# Build application image if needed
docker build -t fintaxgpt-rag:latest -f ../Dockerfile ..

# Save images to tar archive
docker save -o fintax-rag-images.tar fintaxgpt-rag:latest pgvector/pgvector:0.8.6-pg17-bookworm
```

### On Developer Machine (Importing):
```sh
docker load -i fintax-rag-images.tar
docker compose up -d
```

---

## 6. Exporting the Database Dump (`pg_dump`)

To create or refresh `postgres-data.sql.gz` from an existing PostgreSQL container:

```sh
# Using the repo helper script:
./../scripts/export_postgres_dump.sh fintax-rag-local/postgres-data.sql.gz

# Or manually via docker exec:
docker exec -t <container_name> pg_dump \
  -U fintaxgpt \
  -d fintaxgpt \
  --clean \
  --if-exists \
  --no-owner \
  --no-privileges | gzip > postgres-data.sql.gz
```

---

## 7. Security & Key Rotation Checklist

1. **Never commit `.env` or `postgres-data.sql.gz`** to git.
2. **Revoke and rotate credentials**: If real API keys (OpenAI, Isaacus, Resend, database passwords) were previously exposed in chat or unencrypted files, revoke them immediately in their respective provider consoles before distributing any bundle.
3. Verify `.env` is listed in `.gitignore`.
