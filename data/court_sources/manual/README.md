# Manual official judgment files

Place browser-downloaded official HCA `.pdf` or `.docx` judgment files here. Do not add
summaries, third-party copies, HTML save bundles, or renamed non-judgment files.

Calculate each digest with:

```bash
shasum -a 256 data/court_sources/manual/<file>
```

Copy `../hca_manual.example.json`, add one entry per file, and pin that digest in
`expected_sha256`. The original official HCA page remains `official_source_url`; the raw
file, its digest, neutral citation, and paragraph locators are preserved in the output.
