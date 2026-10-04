# Production readiness audit — 2026-09-30

**Disposition: broad production blocked.** This source audit supersedes claims that
only organic usage remains. Historical benchmark artifacts are not new validation
of the changed code. No production deployment was performed.

## Follow-up repairs

See [the repair report](PRODUCTION_REPAIR_REPORT_2026-09-30.md) for the subsequent
implementations, 168-test verification and remaining live/deployment blockers. The
findings below describe the source snapshot at the initial audit, before those repairs.

## Verified source findings at initial audit

| Finding | Source | Release implication |
| --- | --- | --- |
| Default generation extracts leading evidence sentences; it makes no LLM request. | `services/generation/adapters.py` | Implement and evaluate a configured production generation adapter. |
| The Jev judge calculates lexical overlap and assigns fixed completeness scores. | `services/verification/judge.py` | Current scores are heuristic proxies, not calibrated Jev model judgments. |
| Jev reranking uses local lexical/authority heuristics. | `services/reranking/jev.py` | Do not report this path as a remote Jev experiment. |
| Telemetry collects in process and serializes JSON; the inspected collector has no OTLP transport. | `packages/telemetry/collector.py` | Demonstrate authenticated delivery to Langfuse, redaction, failure handling and retention. |
| API application and route modules are placeholders. | `apps/api/__init__.py`, `apps/api/routes/__init__.py` | Implement and test authenticated request boundaries before public serving. |
| Claim citation membership is counted as support; jurisdiction labels are counted under a jurisdiction/version metric. | `services/evaluation/generation.py` | These metrics do not establish factual entailment or point-in-time legal correctness. |
| Pilot citation/version success derives from validation success or abstention. | `services/evaluation/pilot.py` | Independent expected-source/version evidence and reviewed answers are needed. |
| Environment checks infer PITR from WAL level and versioned storage from local manifest fields. | `scripts/verify_pilot_environment.py` | These checks do not establish WAL archival/recovery or deployed object-store versioning. |

## Repairs made

- Repair preserves unresolved claim evidence rather than assigning the first available
  citation, removing invalid IDs, or declaring validation errors resolved. The existing
  bounded pipeline now rejects those drafts and returns an abstention.
- Generated answers without verifiable claims fail validation. Duplicate evidence IDs,
  duplicate/empty claim IDs, and missing source URL or parent lineage also fail.
- RLS role-switch, tenant-setting and cleanup errors propagate and close the connection
  instead of silently continuing with uncertain privileges.
- Regression coverage exercises invalid and mixed citation IDs through the full answer
  pipeline, malformed evidence lineage, and failed RLS entry/cleanup/recovery.

These checks validate structure and isolation failures; they do not prove that prose is
entailed by evidence. Existing non-empty citation IDs alone remain insufficient for that.

## Work required before release

1. Confirm production generator/judge providers and deployment destination; implement
   typed adapters with actual model calls and truthful usage accounting.
2. Implement and verify OTLP delivery to the configured Langfuse instance.
3. Complete the authenticated API boundary and enforce tenant/matter scope through it;
   assess transactional pool reset behavior and deployed least-privilege credentials.
4. Validate temporal source correctness and claim support against independent labels;
   review the frozen scope/adequacy heuristics without tuning on held-out cases.
5. Replace readiness proxies with deployed recovery, privacy, concurrency and outage
   evidence. Run restore drills in an isolated database, not the active corpus database.
6. Re-run affected phase evaluations, retain old reports as historical evidence, then
   conduct organic trials and obtain release approval. No accuracy target is promised.

The repository contains extensive pre-existing uncommitted work. This audit did not
reset it, alter the frozen corpus or retrieval settings, or overwrite baseline reports.
