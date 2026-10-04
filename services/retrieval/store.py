"""PostgreSQL exact, lexical and HNSW first-stage retrieval."""

import json

import psycopg

from .models import Candidate


FIELDS = "chunk_id, document_id, version_id, source_locator, authority_rank"
QUERY_CTE = "query AS (SELECT websearch_to_tsquery('english', %s) value)"


class SearchStore:
    def __init__(self, connection: psycopg.Connection) -> None:
        self.connection = connection

    def exact(self, query: str, identifiers: tuple[str, ...],
              limit: int, prefer_court_opening: bool = False) -> tuple[Candidate, ...]:
        if not identifiers:
            return ()
        rows = self.connection.execute(
            f"""WITH {QUERY_CTE}
                SELECT {', '.join('rc.' + item for item in FIELDS.split(', '))},
                       ((10 * max(CASE ei.identifier_type
                           WHEN 'citation' THEN 4 WHEN 'section' THEN 3
                           WHEN 'document_title' THEN 2 ELSE 1 END)
                        + count(*) + ts_rank_cd(rc.search_vector, query.value))::float
                       + CASE WHEN %s AND rc.source_class='court_decision'
                                  AND rc.source_locator->>'section_id'='para_1'
                              THEN 100 ELSE 0 END) AS score
                FROM exact_identifiers ei
                JOIN retrieval_chunks rc USING (chunk_id)
                CROSS JOIN query
                WHERE ei.normalized_identifier = ANY(%s) AND rc.is_active
                GROUP BY {', '.join('rc.' + item for item in FIELDS.split(', '))}, query.value,
                         rc.search_vector, rc.source_class
                ORDER BY score DESC, rc.authority_rank NULLS LAST, rc.chunk_id
                LIMIT %s""",
            (query, prefer_court_opening, list(identifiers), limit),
        ).fetchall()
        return _candidates(rows)

    def resolved_identifiers(self, identifiers: tuple[str, ...]) -> frozenset[str]:
        if not identifiers:
            return frozenset()
        rows = self.connection.execute(
            "SELECT DISTINCT normalized_identifier FROM exact_identifiers "
            "WHERE normalized_identifier = ANY(%s)", (list(identifiers),),
        ).fetchall()
        return frozenset(str(row[0]) for row in rows)

    def lexical(self, query: str, limit: int) -> tuple[Candidate, ...]:
        rows = self.connection.execute(
            f"""WITH {QUERY_CTE}
                SELECT {FIELDS}, ts_rank_cd(search_vector, query.value)::float AS score
                FROM retrieval_chunks, query
                WHERE is_active AND search_vector @@ query.value
                ORDER BY score DESC, authority_rank NULLS LAST, chunk_id
                LIMIT %s""",
            (query, limit),
        ).fetchall()
        return _candidates(rows)

    def dense(self, vector: tuple[float, ...], profile_id: str,
              limit: int, ef_search: int) -> tuple[Candidate, ...]:
        self.connection.execute("SELECT set_config('hnsw.ef_search', %s, true)",
                                (str(ef_search),))
        vector_text = "[" + ",".join(format(value, ".9g") for value in vector) + "]"
        rows = self.connection.execute(
            f"""SELECT {', '.join('rc.' + item for item in FIELDS.split(', '))},
                       1.0 - dense.distance AS score
                FROM (SELECT chunk_id, embedding <=> %s::vector AS distance
                      FROM chunk_embeddings WHERE profile_id = %s
                      ORDER BY embedding <=> %s::vector LIMIT %s) dense
                JOIN retrieval_chunks rc USING (chunk_id)
                WHERE rc.is_active ORDER BY dense.distance, rc.chunk_id""",
            (vector_text, profile_id, vector_text, limit),
        ).fetchall()
        return _candidates(rows)


def _candidates(rows) -> tuple[Candidate, ...]:
    return tuple(Candidate(
        chunk_id=str(row[0]).strip(), document_id=str(row[1]), version_id=str(row[2]),
        source_locator=row[3] if isinstance(row[3], dict) else json.loads(row[3]),
        authority_rank=row[4], retrieval_score=float(row[5]),
    ) for row in rows)
