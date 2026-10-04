"""Fail-closed query routing and Phase 3 hybrid retrieval orchestration."""

from collections.abc import Callable

from packages.security import PermissionScope, resolve_and_enforce_scope
from packages.telemetry import span
from .fusion import reciprocal_rank_fusion
from .identifiers import extract_identifiers, lexical_terms, prefers_court_opening
from .models import RetrievalSettings, SearchResult
from .store import SearchStore

QueryEmbedder = Callable[[str], tuple[float, ...]]


class HybridRetriever:
    def __init__(self, store: SearchStore,
                 settings: RetrievalSettings = RetrievalSettings()) -> None:
        self.store = store
        self.settings = settings

    def search(self, query: str, embed_query: QueryEmbedder,
               limit: int = 20,
               permission_scope: PermissionScope | None = None) -> SearchResult:
        if not query.strip():
            raise ValueError("query must not be empty")
        scope = resolve_and_enforce_scope(permission_scope)
        with span("retrieval", {"settings_version": self.settings.version, "tenant_id": scope.tenant_id}):
            with span("query_parse"):
                identifiers = extract_identifiers(query)
                lexical_query = lexical_terms(query)
                resolved = self.store.resolved_identifiers(identifiers)
            if identifiers and resolved != frozenset(identifiers):
                return SearchResult(query, "unresolved_exact_identifier", identifiers, (),
                                    self.settings.version)
            with span("exact_retrieval"):
                exact = self.store.exact(lexical_query, identifiers, self.settings.exact_limit,
                                         prefers_court_opening(identifiers))
            with span("lexical_retrieval"):
                lexical = self.store.lexical(lexical_query, self.settings.lexical_limit)
            with span("query_embedding"):
                vector = embed_query(query)
            with span("dense_hnsw"):
                dense = self.store.dense(vector, self.settings.profile_id,
                                         self.settings.dense_limit, self.settings.hnsw_ef_search)
            with span("rrf_fusion"):
                rankings = {"exact": exact, "lexical": lexical, "dense": dense}
                chunks = reciprocal_rank_fusion(rankings, self.settings, limit)
            route = "exact_hybrid" if identifiers else "hybrid"
            return SearchResult(query, route, identifiers, chunks, self.settings.version)
