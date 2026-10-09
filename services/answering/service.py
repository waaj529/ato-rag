"""Public-corpus answer use case with authenticated scope and frozen retrieval settings."""

from dataclasses import asdict

from packages.security import scope_context, ScopeSafetyPolicyGate
from services.context_builder import ContextBuilder, Phase4Store
from services.generation import ModelRouter
from services.reranking import ChildReranker
from services.retrieval import HybridRetriever, SearchStore
from services.source_registry import CorpusScopeGate, ScopeStatus
from services.verification import GroundedAnswerPipeline
from .database import request_connection
from .providers import request_providers
from .query_normalization import expand_official_acronyms


class AnswerService:
    def __init__(self, pool, isaacus_key, generator):
        self.pool, self.isaacus_key, self.generator = pool, isaacus_key, generator

    def execute(self, request, scope, answer=True):
        query, matter_id = expand_official_acronyms(request.query), request.matter_id
        policy = ScopeSafetyPolicyGate().evaluate(query)
        scope_decision = CorpusScopeGate().evaluate(query)
        if not policy.passed or scope_decision.status == ScopeStatus.OUT_OF_CORPUS:
            return {"abstained": True, "reason": policy.code if not policy.passed else scope_decision.code}
        with (scope_context(scope), request_connection(self.pool, scope, matter_id) as conn,
              request_providers(self.isaacus_key) as (embedder, adapter)):
            result = HybridRetriever(SearchStore(conn)).search(query, embedder.embed_query,
                                                               limit=80, permission_scope=scope)
            if not answer:
                return {"retrieval": asdict(result), "corpus": "PUBLIC_OFFICIAL"}
            store = Phase4Store(conn)
            reranker = ChildReranker(store, adapter)
            context = ContextBuilder(store).build(reranker.rerank(result))
            pipeline = GroundedAnswerPipeline(router=ModelRouter(self.generator))
            response = pipeline.run(query, context, permission_scope=scope)
            return {"response": asdict(response), "corpus": "PUBLIC_OFFICIAL",
                    "validation_scope": "structural; semantic and temporal validation pending"}
