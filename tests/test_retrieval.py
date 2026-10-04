"""Phase 3 identifier routing, RRF and passage-recall tests."""

from collections import Counter

from services.evaluation.failure_classes import CLASSIFICATIONS
from services.evaluation.retrieval import RetrievalBenchmark, relevant_rank
from services.retrieval import Candidate, HybridRetriever, RetrievalSettings
from services.retrieval.fusion import reciprocal_rank_fusion
from services.retrieval.identifiers import (
    extract_identifiers, lexical_terms, normalize_identifier, prefers_court_opening,
)
from services.retrieval.models import SearchResult


def _candidate(chunk_id="a", document_id="doc", start=0, end=100, score=1.0):
    return Candidate(chunk_id, document_id, "v1",
                     {"section_id": "s1", "char_start": start, "char_end": end}, 10, score)


def test_identifier_extraction_normalizes_legal_citations_and_pinpoints():
    query = "What do TR 2022/3, section 40-10 and [2025] HCA 30 at [12] provide?"
    assert extract_identifiers(query) == ("tr20223", "2025hca30", "4010", "para12")
    assert extract_identifiers("ITAR 2021 s 1000-1.08") == ("1000108",)
    assert lexical_terms("What does TR 2022/3 conclude about Personal services income?") == (
        "personal services income"
    )
    assert lexical_terms("How is Tax file number treated for tax purposes?") == (
        "tax file number tax"
    )
    assert prefers_court_opening(("2025hca30",)) is True
    assert prefers_court_opening(("2025hca30", "para12")) is False
    assert normalize_identifier("C2026C00324#108-5") == "c2026c003241085"


def test_rrf_fuses_rankings_with_exact_boost():
    exact = (_candidate("a"),)
    lexical = (_candidate("b"), _candidate("a"))
    dense = (_candidate("b"),)
    fused = reciprocal_rank_fusion(
        {"exact": exact, "lexical": lexical, "dense": dense}, RetrievalSettings(), 2
    )
    assert fused[0].candidate.chunk_id == "a"
    assert fused[0].ranks == {"exact": 1, "lexical": 2}


def test_unresolved_explicit_identifier_fails_closed_without_embedding():
    class Store:
        resolved_identifiers = staticmethod(lambda identifiers: frozenset())

    called = False

    def embed(query):
        nonlocal called
        called = True
        return (0.0,) * 768

    result = HybridRetriever(Store()).search("What does TR 2099/999 provide?", embed)
    assert result.route == "unresolved_exact_identifier"
    assert result.chunks == ()
    assert called is False


def test_passage_recall_requires_containing_source_span():
    case = {"must_abstain": False, "expected_passages": [{
        "document_id": "doc", "version_id": "v1", "section_id": "s1",
        "char_start": 20, "char_end": 80,
    }]}
    result = SearchResult("q", "hybrid", (), (
        type("Hit", (), {"candidate": _candidate(start=30, end=90)})(),
        type("Hit", (), {"candidate": _candidate("b", start=0, end=100)})(),
    ), "v1")
    assert relevant_rank(case, result) == 2
    benchmark = RetrievalBenchmark()
    benchmark.add(case, result)
    assert benchmark.report()["positive"]["recall_at_1"] == 0.0
    assert benchmark.report()["positive"]["recall_at_5"] == 1.0


def test_reviewed_failure_classes_cover_the_frozen_31_misses():
    assert len(CLASSIFICATIONS) == 31
    assert Counter(value[0] for value in CLASSIFICATIONS.values()) == {
        "benchmark_defect": 10, "long_authority_chunk_context": 9,
        "dense_miss": 7, "lexical_miss": 3, "fusion_problem": 1,
        "identifier_resolution_failure": 1,
    }
