"""Bounded request transport for existing Isaacus adapters; baseline algorithms unchanged."""

from contextlib import contextmanager

import httpx

from services.embedding import IsaacusEmbeddingClient
from services.reranking import IsaacusRerankingClient, KanonRerankerAdapter


@contextmanager
def request_providers(api_key):
    with httpx.Client(timeout=30, follow_redirects=False) as client:
        def transport(request, timeout):
            response = client.post(request.full_url, content=request.data, headers=dict(request.header_items()))
            if response.status_code != 200:
                raise RuntimeError(f"Isaacus request failed: HTTP {response.status_code}")
            return response.content
        yield (
            IsaacusEmbeddingClient(api_key, timeout=30, transport=transport),
            KanonRerankerAdapter(IsaacusRerankingClient(api_key, transport=transport)),
        )
