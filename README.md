# FinTaxGPT RAG

This repository implements the architecture in
`FintaxGPT_Production_RAG_Architecture_2027.md` incrementally.

The current implementation covers the Phase 2 handoff:

- register and verify the cleaned `ready-document-1.0` corpus without copying it;
- build deterministic, structure-aware parent and child chunks;
- emit narrative and structured-table chunks separately;
- preserve source, version, legal classification and locator metadata through
  a normalized document catalog and chunk lineage;
- validate chunk identity, lineage and size limits.

## Import and chunk the corpus

```bash
python3 scripts/import_ready_corpus.py \
  --source "/Users/mac/Ato website scraper/ato_data/ready_for_chunking"

python3 scripts/chunk_corpus.py
python3 scripts/verify_chunks.py
```

The source location can be overridden with `FINTAX_READY_CORPUS`. Generated
catalog, parent and child shards are gzip-compressed JSONL under
`data/chunks/ato_ready/`. This stage does not create embeddings or load a
vector database.
