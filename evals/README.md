# Evaluations

`australia_tax_legal_gold.jsonl` contains the first 300 deterministic review
candidates for Phase 0. Every expected passage is an exact character span in the
immutable `ready-document-1.0` corpus and must fit wholly inside one child chunk.
The validator resolves evidence across the registered ATO and official High Court
manifests; nine positive cases are grounded in court decisions.

Locators name the identifiers the chunker actually emits, so a legislation passage is
addressed as `C2026C00324#108-5` rather than by the upstream placeholder, and a ruling
named in a question is the citation resolved from source evidence (`TR 2006/2`, not the
corrupted `TR 20/06` the source file stored).

The questions are source-derived starting points, not domain-approved claims.
The current set is a `waived_not_performed` engineering benchmark. Its hash-bound
project-owner waiver permits continued development but is not professional validation.
If professional review becomes available, the reviewer may edit the gold file and replace
the waiver with a hash-bound approval in `domain_review_approval.json`. Professional-review
and professional-pilot claims remain blocked until then.

`phase2/golden_ready_document_chunker.jsonl` freezes 11 representative corpus
handoffs and their chunk outputs across every available source class, structured
tables, historical guidance and long-section splitting. This validates the
imported parsed-document contract and Phase 2 chunker implementation. Raw parser
artifacts are an upstream handoff and are not a local gate condition.

Run the fail-closed gate with:

```bash
python3 scripts/verify_phase2_gate.py
```

Engineering progression is authorized when all technical checks pass and the review
governance record is either professionally approved or validly waived. The report keeps
technical verification, waiver status, qualified review and professional-pilot authorization
separate so the absent professional review is never concealed.
