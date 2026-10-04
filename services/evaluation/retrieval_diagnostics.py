"""Channel-level evidence for Phase 3 retrieval misses."""

from dataclasses import asdict

import psycopg

from services.retrieval import RetrievalSettings, SearchStore
from services.retrieval.fusion import reciprocal_rank_fusion
from services.retrieval.identifiers import extract_identifiers, lexical_terms
from services.retrieval.models import Candidate, SearchResult

from .retrieval import relevant_rank


def _passage_rank(case: dict, values: tuple[Candidate, ...]) -> int | None:
    chunks = tuple(type("Hit", (), {"candidate": value})() for value in values)
    return relevant_rank(case, SearchResult(case["question"], "diagnostic", (), chunks, "diagnostic"))


def _document_rank(document_id: str, values: tuple[Candidate, ...]) -> int | None:
    return next((rank for rank, value in enumerate(values, 1)
                 if value.document_id == document_id), None)


def _expected_chunks(connection: psycopg.Connection, passage: dict) -> list[dict]:
    rows = connection.execute(
        """SELECT rc.chunk_id, rc.is_active,
                  EXISTS (SELECT 1 FROM chunk_embeddings ce
                          WHERE ce.chunk_id=rc.chunk_id AND ce.profile_id='kanon2-768-v1'),
                  rc.source_locator
           FROM retrieval_chunks rc
           WHERE rc.document_id=%s AND rc.version_id=%s
             AND rc.source_locator->>'section_id'=%s
             AND (rc.source_locator->>'char_start')::int <= %s
             AND (rc.source_locator->>'char_end')::int >= %s
           ORDER BY ((rc.source_locator->>'char_end')::int
                   - (rc.source_locator->>'char_start')::int), rc.chunk_id""",
        (passage["document_id"], passage["version_id"], passage["section_id"],
         passage["char_start"], passage["char_end"]),
    ).fetchall()
    return [{"chunk_id": str(row[0]).strip(), "active": row[1],
             "embedding_present": row[2], "source_locator": row[3]} for row in rows]


def diagnose_case(connection: psycopg.Connection, case: dict,
                  vector: tuple[float, ...]) -> dict:
    settings = RetrievalSettings()
    store = SearchStore(connection)
    query = case["question"]
    identifiers = extract_identifiers(query)
    terms = lexical_terms(query)
    resolved = store.resolved_identifiers(identifiers)
    exact_all = store.exact(terms, identifiers, 2000)
    lexical_all = store.lexical(terms, 2000)
    dense_all = store.dense(vector, settings.profile_id, 1000, 1000)
    exact = exact_all[:settings.exact_limit]
    lexical = lexical_all[:settings.lexical_limit]
    dense = store.dense(vector, settings.profile_id, settings.dense_limit,
                        settings.hnsw_ef_search)
    rankings = {"exact": exact, "lexical": lexical, "dense": dense}
    fused = reciprocal_rank_fusion(rankings, settings, 1000)
    fused_result = SearchResult(query, "diagnostic", identifiers, fused, settings.version)
    passage = case["expected_passages"][0]
    expected_chunks = _expected_chunks(connection, passage)
    document_id = passage["document_id"]
    document_chunk_count = connection.execute(
        "SELECT count(*) FROM retrieval_chunks WHERE document_id=%s AND is_active",
        (document_id,),
    ).fetchone()[0]
    return {
        "case_id": case["id"], "question": query, "category": case["category"],
        "expected_document": document_id, "expected_version": passage["version_id"],
        "expected_locator": {key: passage.get(key) for key in
                             ("section_id", "char_start", "char_end")},
        "expected_chunks": expected_chunks, "expected_document_chunks": document_chunk_count,
        "identifiers": list(identifiers),
        "unresolved_identifiers": sorted(set(identifiers) - resolved),
        "production_ranks": {"exact": _passage_rank(case, exact),
                             "lexical": _passage_rank(case, lexical),
                             "dense": _passage_rank(case, dense),
                             "fused": relevant_rank(case, fused_result)},
        "diagnostic_ranks": {"exact": _passage_rank(case, exact_all),
                             "lexical": _passage_rank(case, lexical_all),
                             "dense": _passage_rank(case, dense_all)},
        "document_ranks": {"exact": _document_rank(document_id, exact_all),
                           "lexical": _document_rank(document_id, lexical_all),
                           "dense": _document_rank(document_id, dense_all)},
        "settings": asdict(settings),
    }
