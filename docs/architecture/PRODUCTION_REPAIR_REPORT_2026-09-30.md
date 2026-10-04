# Production repair report — 2026-09-30

**Broad production remains blocked.** The audited application integrations now have
concrete implementations and regression coverage. Live provider/deployment verification
and independent product accuracy have not been completed. No deployment was performed.

## Implemented and checked

| Area | Current implementation | Current evidence |
| --- | --- | --- |
| Generation | Configurable HTTPS structured LLM adapter; provider-reported model/usage; estimated or unknown cost; real bounded repair; no default extractive fallback | Provider contract tests cover success, refusal, truncation, malformed schema/usage, outage and repair |
| Jev proxies | `HeuristicEvidenceJudge`, `HeuristicReranker`, provider-neutral signal types; no fake Jev model observations | Proxy regression tests; no real Jev endpoint/API configured |
| Langfuse | Authenticated OTLP/HTTP JSON, epoch timestamps, model child spans, metadata allowlist, failure/partial-rejection handling | HTTP contract, privacy, hierarchy, concurrent isolation and exceptional-exit tests; no remote ingestion claim |
| API | `/v1/answer`, `/v1/retrieve`; RS256 signature/issuer/audience/expiry validation; no unsigned-token fallback | Signed/unsigned/expired/invalid audience tests; scope, concurrent requests and export-failure tests |
| Database scope | Transaction-local tenant/matter settings, pool reset, deployment-specific read-only login checks | Actual PostgreSQL concurrent pool isolation and transaction-abort checks in disposable databases; deployment role migration supplied, not applied |
| Evaluation | Independent reviewed propositions, expected authorities/versions/locators/as-of intervals and answer-bound human labels | Negative tests reject unsupported claims with valid citations, wrong versions/dates, stale or incomplete reviews |
| Recovery | Consistent operational-table snapshot; actual isolated restore; content-hash verification; isolated reindex and cleanup | PostgreSQL integration test restores two matters, one document and one job in a disposable fixture; active corpus untouched |
| Release gates | Historical Phase 5 integrity is distinct from current readiness; structural/proxy metrics cannot authorize staging | Historical report hash remains valid; current Phase 5 exits blocked; independent acceptance regression tests |

Verification command:

```sh
.venv/bin/python -m pytest -q --junitxml=data/evaluations/release_repair_tests_20260930.xml
```

Result: **168 passed in 9.13 seconds**. All 189 Python source/test/script files checked
were at or below 150 lines. `git diff --check` passed. Tests used HTTP fixtures for remote
providers and disposable databases for the new recovery/pool integration checks.

The machine-readable report is
[`production_readiness_20260930_repaired.json`](../../data/evaluations/production_readiness_20260930_repaired.json).
It records test-report/source hashes, missing configuration and explicit phase blockers.
No historical Phase 5 or Phase 7 score is reused as validation for changed code.

## Still blocked

- No production generation endpoint, provider/model revision or matching credentials are
  configured. The existing Isaacus credential covers the upstream integration only.
- Real Jev integration is intentionally absent pending an actual configured API contract.
  The remaining heuristic judge is labeled as a proxy and cannot establish entailment.
- No Langfuse project/host is configured. Remote ingestion/readback, retention and deletion
  behavior remain unverified. Export is synchronous and has no durable retry queue.
- No production OIDC issuer/JWKS/audience or least-privilege API database connection is
  configured. The API currently searches public evidence only, not private matter files.
- Independent reviewed gold propositions and exact-response claim labels have not been
  supplied. The evaluation tooling is implemented; factual answer accuracy remains unknown.
- Deployed load limits, distributed quotas, full-corpus recovery, WAL archival/PITR and
  object-storage versioning still need deployment-specific tests. The isolated operational
  restore does not stand in for those checks.
- Phase 5 live model evaluations and Phase 7 real-user trials must be rerun after those
  prerequisites are met. Existing test fixtures are not organic professional validation.

Follow [Production integrations](../runbooks/PRODUCTION_INTEGRATIONS.md) for configuration,
run commands and the independent evaluation/recovery workflows. Broad release remains
blocked; passing local tests cannot authorize it.

The frozen corpus, stored embeddings, HNSW parameters, first-stage retrieval settings and
Kanon reranking algorithm were not changed. Existing benchmark reports remain historical
artifacts. New benchmark writers use new filenames and refuse overwrites.
