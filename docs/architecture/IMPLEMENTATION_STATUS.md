# Architecture implementation status

> **2026-09-30 source audit: production blocked.** Several completion statements below
> describe historical engineering gates rather than implemented production capabilities.
> Real generation, authenticated OTLP export and signed-token API boundaries now have
> implementations and regression tests, but live configuration and validation remain
> missing. Jev proxies are explicitly named heuristics. See the
> [repair report](PRODUCTION_REPAIR_REPORT_2026-09-30.md) for current evidence and blockers.
> Historical benchmark results do not validate the newly changed code.

The governing design is
[`FintaxGPT_Production_RAG_Architecture_2027_Langfuse_Jev.md`](../../FintaxGPT_Production_RAG_Architecture_2027_Langfuse_Jev.md).
Phase names below intentionally match Section 38 of that document.

| Phase | Status | Evidence |
| --- | --- | --- |
| Phase 0 — source registry + gold set | Engineering complete; owner waiver recorded | Registered ATO corpus, nine official High Court judgments and 300 source-exact benchmark candidates pass automated gates. Qualified review was not performed; a hash-bound project-owner waiver permits continued engineering without creating a professional-review claim. |
| Phase 1 — ingestion/versioning | Imported handoff | Verified `ready-document-1.0` data is referenced in place. |
| Phase 2 — parser + parent/child chunking | Technical gate passed | The regenerated ATO and official-court exports pass source-exact chunk, golden-fixture and court-coverage gates. Qualified review was waived by the project owner for continued engineering. |
| Phase 3 — Kanon 2 + PostgreSQL retrieval | Complete; frozen baseline | Verified by `scripts/verify_phase3_exit.py`; first-stage retrieval is frozen during the staging trial. |
| Phase 4 — Kanon reranking + context builder | Complete; frozen for staging | Provider-neutral reranking, parent expansion and context budgeting are implemented and held fixed during staging. |
| Phase 5 — grounded generation + citations | Complete; frozen for staging | Grounded generation, Jev signals and deterministic citation/version validation are implemented and held fixed during staging. |
| Phase 6 — security/ops | Technical gate passed | Security and operational verification are implemented; staging retains the non-professional-validation label. |
| Phase 7 — professional pilot | Safe for staging; usability target open | Safety gate passed on the frozen 35-case scope-gated baseline: 0% false answers and 100% citation and source/version correctness. False abstention is 15% against a target of at most 5%; broad production is not authorized. |

The scope-gated report is frozen as the staging baseline and must not be used for further
threshold tuning. Organic staging queries are labeled `staging / not formal professional
validation`; false abstentions are collected and classified before any bounded adjustment is
considered. Retrieval, reranking, generation, evidence-adequacy and corpus-scope thresholds
remain frozen. A staging result cannot authorize broad production.

`CorpusScopeGate` currently blocks known unindexed regimes conservatively. This is a staging
constraint, not the target source-of-truth design: future scope coverage must derive from the
published source registry/corpus state so publishing a new authority can change scope without
growing a permanent list of authority-specific exclusions.

Phase 3 has a frozen `kanon2-768-v1` input manifest covering 515,290 verified child chunks.
PostgreSQL 17 with pgvector 0.8.6 stores all 515,290 vectors with zero NULLs and fixed
768 dimensions. On 2026-09-26, `chunk_embeddings_hnsw_idx` was built with the documented
baseline (`m=16`, `ef_construction=128`) in 717.70 seconds. The 1,950 MB index is ready and
valid; a representative top-20 cosine plan used the HNSW index and executed in 0.672 ms.
Publication `20ae192d-3848-435e-8643-ec72d56da582` is the sole active publication for the
profile and is bound to completed embedding run `ce866471-846f-4371-ad54-33813e4637be`.

Exact identifiers are atomically derived from document IDs, canonical citations, titles and
source locators. The published mapping contains 1,511,996 rows. Lexical search indexes the
same deterministic legal header/path context supplied to embeddings, plus citation and source
content. The frozen `phase3-rrf-v2` baseline used exact top 20, lexical top 60, dense top 100
and `hnsw.ef_search=200`. Its 31 top-100 misses were inspected channel by channel: 10 benchmark
defects, 9 long-authority/chunk-context failures, 7 dense misses, 3 lexical misses, one fusion
problem and one identifier-priority failure. Every expected chunk was active and embedded;
there were no metadata/filter failures.

The evidence-backed `phase3-rrf-v4` candidate uses exact top 120, lexical top 200, dense top
100 and query-time `hnsw.ef_search=1000`. Citation identifiers outrank broad document-title
matches, and unpinpointed High Court issue queries deterministically prefer paragraph 1.
Embedding dimensions, stored vectors and HNSW construction parameters are unchanged.
Against the same gold hash, Recall@20 improves from 0.807 to 0.833, Recall@60 from 0.870 to
0.907 and Recall@100 from 0.897 to 0.927. Abstention accuracy remains 100%; median latency
increases from 36.4 ms to 67.2 ms while p95 improves from 617.5 ms to 609.4 ms. Recall@5
decreases slightly from 0.650 to 0.647. These results are engineering evidence only: the
benchmark is still unreviewed.

The final benchmark-repair pass changed only five previously confirmed defective or
materially ambiguous cases: `au-tax-0011`, `au-tax-0026`, `au-tax-0040`, `au-tax-0069` and
`au-tax-0084`. The first was rebound from a “read on” lead-in to the source-exact part-year
claim instructions; the other four retained their evidence spans and received substantive,
authority-specific questions. The regenerated 300-case set has SHA-256
`c148aca9600eaaa4748c90e091e3ca967eebed2a3a40668b703409ac90c884a8`.

With retrieval settings unchanged, a warm-cache `phase3-rrf-v4` run records Recall@1 0.470,
Recall@5 0.657, Recall@10 0.767, Recall@20 0.847, Recall@60 0.920 and Recall@100 0.943.
Abstention accuracy remains 1.000; median latency is 76.5 ms and p95 is 684.6 ms. All five
repaired cases now retrieve inside the top 100. The 17 remaining misses classify as nine
fusion problems, four dense misses, three long-authority/chunk-context misses and one lexical
miss; there are no remaining benchmark, identifier-resolution or metadata/filter failures.
Because Recall@60 is below the architecture's suggested 0.980 correct-version Recall@50
production gate, and the misses still expose repeated retrieval-layer patterns, Phase 3 is
not complete and Phase 4 has not started.

On 2026-09-26, the project owner explicitly waived qualified domain review for development
because a qualified reviewer was unavailable and formal external review was deferred. The
waiver is bound to the current benchmark hash and architecture revision
`2026-09-26-domain-review-waiver-1`. Technical use and engineering phase progression are
allowed; qualified professional validation was not performed, the benchmark must not be
described as professionally reviewed, and a professional pilot remains unauthorized. The
only current Phase 3 exit blocker is the retained correct-version Recall@50 target of 0.980.

`evals/australia_tax_legal_gold.jsonl` contains 290 source-exact,
answer-bearing candidates and 10 deliberate malformed-citation abstention
cases. It is a review candidate set, never an approved benchmark until the
hash-bound domain approval record is complete.

The candidate generator now rejects viewer errors, contact directories, ruling-reliance
boilerplate, contaminated footnote/table headings, incomplete method statements, generic
navigation headings, and non-tax Commonwealth statutes. The regenerated set uses 100
tax-statute cases, 61 ATO-guidance cases, 110 ruling/determination/LCR/PCG cases, 10 tax-
regulation cases, 9 High Court cases, and 10 abstention controls. Questions are unique and content-aware;
the former `What position does ...` template is absent. The resulting candidate hash is
`c148aca9600eaaa4748c90e091e3ca967eebed2a3a40668b703409ac90c884a8`.

`evals/phase2/golden_ready_document_chunker.jsonl` freezes 11 representative
parsed-document handoffs and chunk outputs. It validates the imported
`ready-document-1.0` contract and chunker. Raw parsing is an upstream imported
handoff, outside this repository's measurable Phase 2 gate.

## Identifier and metadata repair

Phase 3's exit criterion is "exact identifiers", so every shipped identifier is now either
derived from evidence or explicitly marked as unresolved. Implemented under
`services/source_registry`:

- `identifiers.py` derives canonical citations from source URL evidence. A title can select
  an official short pre-2000 form only when the URL independently corroborates the same
  prefix, year and ruling number. A two-digit year that is a prefix of the source year is the
  split-year corruption (`TR 20/06` + `tr2006-002.pdf` → `TR 2006/2`); one that is a suffix
  is the legitimate pre-2000 form (`TR 97/25`) and is left untouched.
- `sections.py` derives `REGISTER#section` for legislation, requiring `document_id`, the
  `source_url` fragment and `statute_version.register_id` to agree, and preserves the
  upstream value as `source_section_id`.
- `urls.py` and `conflicts.py` give each inventory row a source identity and refuse an
  import in which one recorded version is claimed under two different contents.
- `authority.py` gives draft and withdrawn material non-binding lifecycle status, maps
  evidence-backed ATO Act mirrors into the Commonwealth taxonomy, downgrades guides and
  forms mislabeled as legislation, and uses rank 10 consistently for binding legislation.

The currently registered citation-evidence-v2 baseline contains 40,409 documents:

| Citation resolution | Documents |
| --- | --- |
| `not_evaluated` — outside the citation rule's scope | 39,273 |
| `confirmed` — the title names the stored value verbatim | 620 |
| `normalized` — repaired from the source URL filename | 81 |
| `uncorroborated` — no URL evidence; value retained unchanged | 434 |
| `flagged` — evidence contradicts the stored value; citation dropped | 1 |

Citation-evidence-v3 corrects 122 canonical identifiers in the source view, including
`TR 96/11`, `TR 98/11` and `MT 2012/3`. Those corrections are not claimed as published
chunk metadata until the ATO export is regenerated and re-registered.

Evidence decides what ships: a contradicted citation is dropped, because a wrong citation
is worse than an absent one, while a citation with no evidence either way is retained —
blanking it would destroy a well-formed identifier on the strength of nothing.

Legislation section ids are derived for all 11,347 `leg-` documents. A further 627
documents classified `primary_legislation` inside the `legal_authority` corpus keep the
generic `sec_NNNN` ids: 582 of them carry an anchor section in
`docid=PAC/<act>/<section>`, but those documents hold up to 231 sections each, so the URL
names the anchor and cannot name every section. The remaining 28,435 documents are
whole-page guidance whose section ids are generic by construction.

`page_status` is now carried on every child chunk, so a document's currency is visible
downstream instead of being dropped at the source boundary. Measured across the corpus:
`current` 28,320, `in_force` 11,347, `draft` 325, `consolidated` 280, `withdrawn` 81,
`superseded` 56. Table chunks are also validated against the projected content of the rows
they claim rather than only a numeric range.

The importer now fails closed on unindexed document files as well as on version conflicts.
The registered corpus contains 7,127 document files that no index lists, so re-importing
it is refused: the *chunking* step is reproducible from the frozen import manifest, but the
*registration* step is not reproducible under this gate.

Run the current Phase 2 gate with:

```bash
python3 scripts/verify_phase2_gate.py
```

A passing technical report authorizes provisional Phase 3 retrieval work. The report
separately exposes benchmark review and professional-pilot authorization.

## Official court ingestion

`services/court_ingestion` is a separate upstream adapter for an explicitly reviewed
Federal Court/High Court seed list. It allowlists official hosts, corroborates the neutral
citation from the fetched page, preserves numbered paragraph pinpoints, writes an atomic
verified `ready-document-1.0` corpus, and hands that corpus to the existing importer.
The adapter and its controlled fixtures pass. On 2026-09-24 all nine reviewed HCA tax
seeds were fetched as official PDFs, parsed, registered and chunked. The verified court
export contains 1,422 parents and 1,423 exact-locator children; the fail-closed audit is
`data/imports/court_ready_attempt.json`. Court coverage now passes.
For the small benchmark unblock, the same adapter also accepts manually downloaded
official HCA PDF/DOCX files through a hash-pinned manifest. This remains a transport fallback,
not another source adapter: official URL validation, parsing, provenance, output contract,
verification, and importer registration remain unchanged.

The full export verifies with `python3 scripts/verify_chunks.py`, which exits 0 and reports
`valid: true` with no failures: every one of the 412,052 narrative children reproduces its
source text as an exact canonical character span, and every one of the 102,094 table
children matches the projected content of the rows it claims.
