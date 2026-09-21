# Architecture implementation status

The governing design is
[`FintaxGPT_Production_RAG_Architecture_2027.md`](../../FintaxGPT_Production_RAG_Architecture_2027.md).
Changes must preserve its evidence-lineage, temporal, authority, security and
fail-closed rules.

| Phase | Status | Current artifact |
|---|---|---|
| Phase 0 — source registry + gold set | Partial | ATO corpus registration exists; domain gold set remains future work |
| Phase 1 — ingestion/versioning | Imported handoff | Verified `ready-document-1.0` data is referenced in place |
| Phase 2 — parser + parent/child chunking | Active | `services/chunker`, import/chunk/verify CLIs |
| Phase 3 — embedding + PostgreSQL retrieval | Not started | Package boundaries only |
| Phase 4 — reranking + context builder | Not started | Package boundaries only |
| Phase 5 — generation + citations | Not started | Package boundaries only |
| Phase 6 — security/operations | Not started | Package boundaries only |
| Phase 7 — professional pilot | Not started | — |

The current chunk token counts use deterministic `unicode-lexical-v1` sizing.
Before Phase 3 sends text to Kanon 2, the embedding adapter must calculate the
provider/model token count and fail loudly on overflow.

