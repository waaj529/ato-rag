"""Phase 4 reranker adapter, dedupe and ordering tests."""

import json

from packages.telemetry import get_global_collector
from services.reranking import (
    ChildReranker,
    HydratedCandidate,
    IsaacusRerankingClient,
    HeuristicReranker,
    KanonRerankerAdapter,
)
from services.reranking.dedupe import dedupe_candidates
from services.retrieval import Candidate, RetrievedChunk, SearchResult


def _hydrated(chunk_id: str, text: str, rank: int = 1, source: str = "public_ruling") -> HydratedCandidate:
    cand = Candidate(chunk_id, "doc", "v1", {"section_id": "s1"}, 10, 1.0)
    retrieved = RetrievedChunk(cand, 0.1, {"dense": rank})
    return HydratedCandidate(retrieved, f"parent-{chunk_id}", source, None, "header", text, f"header\n\n{text}")


def test_reranking_client_validates_and_preserves_provider_order():
    captured = {}

    def transport(request, timeout):
        captured.update(json.loads(request.data))
        return json.dumps({
            "results": [{"index": 1, "score": 0.9}, {"index": 0, "score": 0.2}],
            "usage": {"input_tokens": 12},
        }).encode()

    result = IsaacusRerankingClient("secret", transport=transport).rerank("tax question", ["first", "second"], 2)
    assert captured["model"] == "kanon-2-reranker"
    assert captured["top_n"] == 2
    assert result.results == ((1, 0.9), (0, 0.2))
    assert result.input_tokens == 12


def test_near_duplicate_candidates_keep_the_best_first_stage_hit():
    first = _hydrated("a", "The taxpayer may deduct the qualifying legal expense.")
    duplicate = _hydrated("b", "The taxpayer may deduct the qualifying legal expense!")
    distinct = _hydrated("c", "A capital gain arises when the CGT event happens.")
    assert dedupe_candidates((first, duplicate, distinct), 0.95) == (first, distinct)


def test_kanon_and_heuristic_adapters_interchangeable():
    collector = get_global_collector()
    collector.clear()
    first = _hydrated("a", "deductible travel expenses between sites", 1, "legislation")
    second = _hydrated("b", "table of contents and notices", 2, "guidance")

    def transport(req, t):
        return json.dumps({
            "results": [{"index": 0, "score": 0.85}, {"index": 1, "score": 0.15}],
            "usage": {"input_tokens": 20},
        }).encode()

    kanon = KanonRerankerAdapter(IsaacusRerankingClient("key", transport=transport))
    jev = HeuristicReranker()

    k_children, k_tokens = kanon.rerank_candidates("travel deduction", (first, second), 2)
    assert len(k_children) == 2
    assert k_children[0].candidate.retrieved.candidate.chunk_id == "a"
    assert k_tokens == 20

    j_children, j_tokens = jev.rerank_candidates("travel deduction", (first, second), 2)
    assert len(j_children) == 2
    assert j_children[0].candidate.retrieved.candidate.chunk_id == "a"
    assert j_children[0].signals is not None
    assert j_children[0].signals.relevant > j_children[1].signals.relevant

    obs = collector.get_observations()
    assert len(obs) == 1
    assert {o.provider for o in obs} == {"isaacus"}
