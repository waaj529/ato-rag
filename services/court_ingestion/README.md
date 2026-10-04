# Official court ingestion

This package is an upstream adapter. It fetches only explicitly seeded HTTPS pages from
the Federal Court or High Court allowlist, corroborates the seeded medium-neutral
citation against the official page, preserves numbered paragraphs, and emits a verified
`ready-document-1.0` corpus. It has no dependency on chunking, embeddings, or retrieval.

Seed files are JSON arrays:

```json
[
  {
    "source_url": "https://www.judgments.fedcourt.gov.au/...",
    "court": "Federal Court of Australia",
    "neutral_citation": "[YYYY] FCA NNN"
  }
]
```

For a browser-downloaded official PDF/DOCX, use `local_file`, `official_source_url`, and
the file's lowercase `expected_sha256` instead of `source_url`. Local paths are resolved
relative to the manifest and may not escape that directory. See
`data/court_sources/hca_manual.example.json`.

Build into a new path; existing output is never replaced:

```bash
python3 scripts/build_court_corpus.py \
  --seeds data/court_sources/hca_tax_seed.json \
  --output data/source_snapshots/court_ready \
  --audit data/imports/court_ready_attempt.json
```

Register the verified result through the existing importer contract:

```bash
python3 scripts/import_ready_corpus.py \
  --source data/source_snapshots/court_ready \
  --config packages/config/corpora/court_ready.json \
  --output data/imports/court_ready.json \
  --inventory data/imports/court_ready_inventory.jsonl.gz
```

The fetcher deliberately fails on anti-bot challenge pages, missing citation evidence,
unnumbered judgments, redirects to non-official hosts, non-HTML responses, or oversized
responses. Do not substitute AustLII or another secondary host for an official judgment.
