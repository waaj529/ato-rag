# Production integration configuration and verification

Broad production remains blocked. The configurable API can be tested in staging once
its dependencies are supplied. No provider/model, region, identity issuer or retention
policy has been selected on the owner's behalf.

## Generation

Set these through the deployment secret manager/environment:

- `FINTAX_LLM_ENDPOINT`: full HTTPS OpenAI-compatible `/v1/chat/completions` endpoint.
- `FINTAX_LLM_API_KEY`: the corresponding provider credential, not an Isaacus key.
- `FINTAX_LLM_PROVIDER`, `FINTAX_LLM_MODEL`, `FINTAX_LLM_REVISION`: actual provider and pinned model/configuration.
- Optional `FINTAX_LLM_INPUT_RATE`, `FINTAX_LLM_OUTPUT_RATE`, `FINTAX_LLM_CACHED_INPUT_RATE`:
  USD per million tokens. These produce a labeled estimate, never an invoiced-cost claim.
  Missing rates mean unknown cost; do not substitute zero.

The endpoint must support strict JSON schema responses. A timeout, refusal, malformed
response, incomplete completion or missing usage fails the request. A bounded repair is
another real provider call. Output prose is rendered from the validated claim list.
A circuit breaker rejects further calls after repeated provider HTTP/transport failures.
`ExtractiveGenerator` is available only through explicit injection for regression fixtures.

## Traces

Configure `LANGFUSE_HOST`, `LANGFUSE_PUBLIC_KEY`, `LANGFUSE_SECRET_KEY`. The exporter sends
HTTP/JSON with Basic authentication to `/api/public/otel/v1/traces`. Export rejection,
partial acceptance and network failure prevent a successful API answer response.
The exporter allowlists operational metadata; it sends no query, evidence, answer,
tenant/user identity or raw exception message. Each model observation is a child span
with epoch timestamps and a valid trace ID. Unknown costs are omitted.

Remote ingestion/readback, retention controls and deletion behavior must be demonstrated
on the actual deployment. Local HTTP mocks prove contract behavior only. There is no
durable retry queue: failed exports fail the request and need operational monitoring.
To defer remote Langfuse ingestion until post-launch, set `FINTAX_TELEMETRY_EXPORTER=noop`
or leave `LANGFUSE_HOST` unset; `NoOpExporter` safely absorbs spans without blocking.

## Identity and database

Configure `FINTAX_OIDC_ISSUER`, `FINTAX_OIDC_AUDIENCE`, `FINTAX_OIDC_JWKS_URL` for the trusted
issuer. Tokens must be RS256-signed and include `sub`, `tid`, `iat`, `exp` and the configured
audience/issuer. Optional `matter_ids` grants are taken only from verified claims.
Issuer provisioning must guarantee these claims cannot be edited by the end user.

Apply `migrations/0007_api_readonly_role.sql` in the deployment database. Provision the
`fintax_api` login secret separately and set `FINTAX_DATABASE_URL` to that login.
The pool rejects superuser/BYPASSRLS/CREATEROLE/CREATEDB credentials and other login names.
It uses transaction-local tenant/matter settings and discards session state on return.
The API serves the frozen public corpus only. It does not search private matter documents.

Run with the project environment:

```sh
.venv/bin/python -m uvicorn apps.api:production_app --factory --host 127.0.0.1 --port 8000
```

Expose `/v1/answer` and `/v1/retrieve` only through the authenticated staging ingress with
TLS and a request-body limit. Bodies contain `query` and optional `matter_id`; tenant,
user, classification and role overrides are rejected. Per-process rate limits do not
replace distributed gateway quotas. Deploying this factory does not authorize release.

## Evaluation and operations

New Phase 5/7 benchmark filenames are distinct from the historical reports. Their
structural/proxy metrics do not assert semantic accuracy. The old Phase 5 verifier now
checks historical artifact integrity but refuses to approve the changed code.

Independently review gold propositions, immutable sources, exact locators and validity
intervals using `ReviewedCase`. Review the exact response with `AnswerReview`; its case
and response hashes bind labels to the evaluated artifacts. `evaluate_reviewed_answers.py`
accepts JSONL records containing `case`, `response` and `review`. Missing labels, stale
hashes, duplicate claims and unenumerated material prose fail rather than improve scores.
No qualified-review claim follows merely from a reviewer ID in a file.

```sh
.venv/bin/python scripts/evaluate_reviewed_answers.py --input reviewed.jsonl --output new-report.json
.venv/bin/python scripts/benchmark_deepeval.py --input data/evaluations/cases.jsonl --output data/evaluations/deepeval_report.json
.venv/bin/python scripts/backup_restore_ops.py --dir /private/new-backup-dir --drill
```

The recovery drill reads a consistent snapshot of three operational tables, creates a
fresh disposable database, restores actual contents, verifies hashes, reindexes there,
and drops that database. It needs database-creation privileges in the drill environment.
It does not prove full-corpus restore, WAL archival/PITR or object-storage versioning.
Those require deployment-specific evidence; existing WAL/manifest proxies stay blocked.

Protocol references: [OpenAI Chat API](https://developers.openai.com/api/reference/resources/chat),
[Langfuse OTLP](https://langfuse.com/integrations/native/opentelemetry),
[PyJWT validation](https://pyjwt.readthedocs.io/en/stable/usage.html),
[Psycopg pooling](https://www.psycopg.org/psycopg3/docs/advanced/pool.html).
