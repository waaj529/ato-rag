"""Phase 3 embedding profile, transport and input-contract tests."""

import gzip
import json

import pytest

from services.embedding import IsaacusEmbeddingClient, iter_batches, iter_chunk_inputs, run_embeddings


def test_isaacus_client_sends_pinned_document_profile():
    captured = {}

    def transport(request, timeout):
        captured["payload"] = json.loads(request.data)
        captured["authorization"] = request.get_header("Authorization")
        captured["timeout"] = timeout
        response = {"embeddings": [{"index": 0, "embedding": [0.0] * 768}],
                    "usage": {"input_tokens": 7}}
        return json.dumps(response).encode()

    result = IsaacusEmbeddingClient("secret", timeout=12, transport=transport).embed_documents(
        ["source-exact legal evidence"]
    )
    assert len(result.vectors[0]) == 768
    assert result.input_tokens == 7
    assert captured["payload"] == {
        "model": "kanon-2-embedder", "texts": ["source-exact legal evidence"],
        "task": "retrieval/document", "overflow_strategy": None, "dimensions": 768,
    }
    assert captured["authorization"] == "Bearer secret"
    assert captured["timeout"] == 12


def test_embedding_client_rejects_bad_batches_and_dimensions():
    client = IsaacusEmbeddingClient("secret", transport=lambda request, timeout: b"{}")
    with pytest.raises(ValueError, match="1 to 128"):
        client.embed_documents([])
    with pytest.raises(ValueError, match="non-empty"):
        client.embed_documents([" "])

    def wrong_dimension(request, timeout):
        return json.dumps({"embeddings": [{"index": 0, "embedding": [0.0]}],
                           "usage": {"input_tokens": 1}}).encode()

    client = IsaacusEmbeddingClient("secret", transport=wrong_dimension)
    with pytest.raises(ValueError, match="dimension"):
        client.embed_query("query")


def test_verified_chunk_inputs_are_hash_bound_and_batched(tmp_path):
    root = tmp_path / "chunks"
    children = root / "children"
    children.mkdir(parents=True)
    (root / "verification_report.json").write_text('{"valid":true}')
    content = "[DOCUMENT: Example]\n\nExact evidence."
    record = {
        "chunk_id": "a" * 64, "chunk_hash": "a" * 64,
        "parent_chunk_id": "b" * 64, "document_id": "doc", "version_id": "v1",
        "source_class": "court_decision", "canonical_reference_id": "[2025] HCA 30",
        "authority_rank": 15, "page_status": "current", "applicable_periods": [],
        "source_locator": {"paragraph_start": 1}, "contextual_header": "[DOCUMENT: Example]",
        "text": "Exact evidence.",
        "content_for_embedding": content, "is_active": True,
    }
    with gzip.open(children / "aa.jsonl.gz", "wt", encoding="utf-8") as handle:
        handle.write(json.dumps(record) + "\n")
    inputs = list(iter_chunk_inputs([root]))
    assert inputs[0].content == content
    assert len(inputs[0].input_sha256) == 64
    assert list(iter_batches(inputs, 1)) == [(inputs[0],)]


@pytest.mark.parametrize("cleanup_error", [OSError("dropped"), KeyboardInterrupt("abort")])
def test_embedding_failure_preserves_original_error_when_cleanup_fails(cleanup_error):
    class Connection:
        def rollback(self):
            raise cleanup_error

    class Store:
        connection = Connection()
        ensure_profile = staticmethod(lambda profile: None)
        total_input_tokens = staticmethod(lambda profile, revision: 0)
        start_run = staticmethod(lambda profile, revision: "run")
        upsert_chunks = staticmethod(lambda batch: None)
        missing = staticmethod(lambda batch, profile: batch)
        finish = staticmethod(lambda run_id, status: (_ for _ in ()).throw(cleanup_error))

    client = IsaacusEmbeddingClient(
        "secret", transport=lambda request, timeout: (_ for _ in ()).throw(RuntimeError("provider"))
    )
    with pytest.raises(RuntimeError, match="provider"):
        run_embeddings([type("Input", (), {"content": "evidence"})()], client, Store(), "revision")
