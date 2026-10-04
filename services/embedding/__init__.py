"""Kanon 2 embedding contracts and verified chunk inputs."""

from .client import EmbeddingBatch, IsaacusEmbeddingClient
from .inputs import ChunkEmbeddingInput, iter_batches, iter_chunk_inputs
from .profile import EmbeddingProfile, KANON2_768_V1
from .runner import run_embeddings

__all__ = [
    "ChunkEmbeddingInput", "EmbeddingBatch", "EmbeddingProfile",
    "IsaacusEmbeddingClient", "KANON2_768_V1", "iter_batches", "iter_chunk_inputs",
    "run_embeddings",
]
