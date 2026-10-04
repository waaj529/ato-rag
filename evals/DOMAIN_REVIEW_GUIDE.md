# FinTaxGPT Domain Review Guide: Phase 0 Benchmark (300 Cases)

## 1. Purpose and governing architecture

Under [`FintaxGPT_Production_RAG_Architecture_2027.md`](../FintaxGPT_Production_RAG_Architecture_2027.md)
(Section 38), continued engineering may use the benchmark after the automated Phase 2 gate
passes and a hash-bound project-owner waiver is recorded. Professional review is still
required before describing the benchmark as professionally approved or starting a
professional pilot.

Parent/child chunking is Phase 2 work. Technical and professional authorization are
reported separately so unavailable review does not block engineering or become hidden.

## 2. Review artifacts

The reviewer has three complementary formats:

1. **Spreadsheet:** [`domain_review_sheet.csv`](./domain_review_sheet.csv)
   - Suitable for Excel, Google Sheets, or Numbers.
   - Contains `reviewer_decision` (`PASS`, `CHANGE`, or `FAIL`) and `reviewer_notes`.
2. **Static HTML reference:** [`domain_review_sheet.html`](./domain_review_sheet.html)
   - A static table for viewing the cases in a browser.
3. **Canonical JSONL:** [`australia_tax_legal_gold.jsonl`](./australia_tax_legal_gold.jsonl)
   - Candidate SHA-256: `c148aca9600eaaa4748c90e091e3ca967eebed2a3a40668b703409ac90c884a8`.

### Candidate-set composition

The set contains 290 unique source-exact, answer-bearing cases and 10 deliberately
malformed-citation negative controls:

- 100 Commonwealth primary-legislation cases;
- 10 Commonwealth regulation cases;
- 110 public ruling, determination, LCR, and PCG cases;
- 61 general ATO guidance cases;
- 9 cases grounded in verified official High Court judgments; and
- 10 negative controls with `must_abstain: true`.

Populated `acceptable_alternatives` are references found in the expected passage. The
reviewer must decide whether each independently supports an acceptable answer; textual
co-occurrence alone is not approval.

## 3. Reviewer rubric

Every case must be evaluated against all four criteria.

### Criterion 1: substantive answer-bearing validity

- Does `expected_passage` directly and sufficiently answer `question`?
- Is the question phrased as an Australian tax or legal practitioner might ask it?
- Are calculations, formulas, and multi-step method statements complete?

### Criterion 2: legal authority and source classification

- Is `source_class` accurate for the source?
- Does `binding_authority` accurately describe the source's legal effect?
- For court decisions, are the court, neutral citation, and proposition accurate?

### Criterion 3: temporal and point-in-time applicability

- Are `applicable_period` and `as_of_date` legally accurate?
- Does the passage apply to the period asked about rather than a superseded or future law?
- Are transitional rules, historical thresholds, and repealed provisions identified correctly?

### Criterion 4: abstentions and alternatives

- Does a fictional, absent, or nonexistent citation require abstention?
- Does each `acceptable_alternatives` entry independently support the proposition?
- Is abstention required where the evidence is insufficient or the law is unsettled?

## 4. Decision categories

Record one decision for every case in `domain_review_sheet.csv`.

| Decision | Meaning | Required action |
| --- | --- | --- |
| **PASS** | Legally sound, answer-bearing, and temporally accurate. | Retain as-is. |
| **CHANGE** | The question, span, or metadata needs refinement. | Describe the exact correction in `reviewer_notes`. |
| **FAIL** | The passage is non-answering, corrupted, boilerplate, or invalid authority. | Replace it with an authentic candidate from the same source class. |

## 5. Review execution and sealing workflow

1. Confirm that `australia_tax_legal_gold.jsonl` matches the baseline SHA-256 above.
2. Confirm that the reviewer holds an applicable Australian legal or tax qualification.
3. Review all 300 cases against all four criteria and record a decision and notes.
4. For every `CHANGE` or `FAIL`, engineering applies the correction or replacement and
   the reviewer reviews the revised case.
5. Recalculate the final benchmark hash:

   ```bash
   shasum -a 256 evals/australia_tax_legal_gold.jsonl
   ```

6. Only after final approval, record the reviewer's real details and final hash in
   [`domain_review_approval.json`](./domain_review_approval.json):

   ```json
   {
     "schema_version": "fintax-domain-review-governance-1.0",
     "status": "approved",
     "gold_sha256": "<FINAL_CALCULATED_HASH>",
     "reviewer_name": "<REVIEWER'S REAL FULL NAME>",
     "reviewer_qualification": "<VERIFIED AUSTRALIAN LEGAL OR TAX QUALIFICATION>",
     "approved_at": "<ACTUAL ISO-8601 APPROVAL TIME>",
     "notes": "Reviewed and approved all 300 benchmark cases across the represented official source classes and negative controls."
   }
   ```

7. Run the release gate:

   ```bash
   python3 scripts/verify_phase2_gate.py
   ```

Phase 3 retrieval work is authorized when both `phase2_chunking_gate_passed` and
`engineering_phase_progression_authorized` are `true`. Under the owner waiver,
`benchmark_review_status` is `waived_not_performed`,
`qualified_professional_review_performed` is `false`, and
`professional_pilot_authorized` remains `false`.

## 6. Waiver-state rule

The project owner waived qualified review for continued development on 26 September 2026
because a qualified reviewer was unavailable and formal external review was deferred. The
waiver is bound to the benchmark hash and architecture revision. Reviewer identity,
qualification and approval time remain empty because no professional approval occurred.
A waiver must never unlock a professional pilot or an approved-benchmark claim.
