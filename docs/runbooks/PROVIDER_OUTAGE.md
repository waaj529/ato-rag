# Model Provider Outage Runbook

## Outage Types & Detection

- **Isaacus Embeddings / Kanon 2 Reranker Outage**:
  - Detection: Consecutive HTTP 5xx / 429 errors trip `CircuitBreaker` (status `OPEN`).
  - Automated Fallback:
    1. Retrieval falls back to exact identifier + lexical FTS search.
    2. Reranking automatically routes to `JevRerankerAdapter` fallback.
- **Jev Decision Judge Outage**:
  - Detection: Circuit breaker trips on Jev decision layer.
  - Automated Behavior:
    - Primary deterministic validators (`DeterministicValidator`) remain authoritative.
    - System marks Jev score as unavailable (`overall_score = None`), records telemetry alert, and allows answer if deterministic validators passed.

## Recovery & Verification

1. Monitor circuit breaker transitioning from `OPEN` to `HALF_OPEN`.
2. Send single probe request to verify provider health.
3. Once consecutive probe calls succeed, circuit resets to `CLOSED`.
