"""Phase 4 parent expansion and token-budget tests."""

from services.context_builder import ContextBuilder, ContextSettings, ParentRecord
from services.reranking import HydratedCandidate, RerankedChild, RerankingResult
from services.retrieval import Candidate, RetrievedChunk


def _child(chunk_id: str, parent_id: str, score: float, rank: int) -> RerankedChild:
    candidate = Candidate(chunk_id, "doc", "v1", {"section_id": chunk_id}, 10, 1.0)
    retrieved = RetrievedChunk(candidate, 0.1, {"dense": rank, "lexical": rank})
    hydrated = HydratedCandidate(retrieved, parent_id, "public_ruling", "TR 2026/1",
                                 "header", "child", "header\n\nchild")
    return RerankedChild(hydrated, score, rank)


def _parent(parent_id: str, units: int) -> ParentRecord:
    return ParentRecord(parent_id, "doc", "v1", "public_ruling", "TR 2026/1", 20,
                        "Ruling", "https://example.test", ("Ruling",), {"section_id": "s"},
                        f"parent text {parent_id}", units)


def test_context_builder_merges_parents_and_enforces_budget():
    children = (_child("a", "p1", 0.9, 1), _child("b", "p1", 0.8, 2),
                _child("c", "p2", 0.7, 3), _child("d", "p3", 0.6, 4))

    class Provider:
        def parents(self, parent_ids):
            return {"p1": _parent("p1", 60), "p2": _parent("p2", 50),
                    "p3": _parent("p3", 30)}

    result = RerankingResult("query", children, 20, "phase4-kanon2-v1")
    context = ContextBuilder(Provider(), ContextSettings(token_budget=100)).build(result)
    assert [item.parent_id for item in context.evidence] == ["p1", "p3"]
    assert context.total_text_units == 90
    assert context.evidence[0].triggering_child_locator == {"section_id": "a"}
    assert context.evidence[0].retrieval_reason == "dense+lexical+reranker"
