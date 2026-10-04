"""Strict Isaacus embeddings API adapter for the Phase 3 profile."""

from dataclasses import dataclass
import json
import time
from typing import Callable, Sequence
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from packages.telemetry import (
    ModelObservation,
    calculate_model_cost,
    get_current_trace_id,
    record_model_observation,
)
from .profile import EmbeddingProfile, KANON2_768_V1


API_URL = "https://api.isaacus.com/v1/embeddings"
MAX_BATCH_SIZE = 128
Transport = Callable[[Request, float], bytes]


@dataclass(frozen=True)
class EmbeddingBatch:
    vectors: tuple[tuple[float, ...], ...]
    input_tokens: int


def _transport(request: Request, timeout: float) -> bytes:
    retries = 8
    backoff = 2.0
    for attempt in range(retries):
        try:
            with urlopen(request, timeout=timeout) as response:
                return response.read()
        except HTTPError as error:
            body = error.read().decode("utf-8", errors="replace")
            if error.code not in {429, 500, 502, 503, 504} or attempt == retries - 1:
                raise ValueError(f"Isaacus API HTTP {error.code}: {body}") from error
            time.sleep(backoff)
            backoff = min(backoff * 2.0, 60.0)
        except (URLError, TimeoutError, ConnectionError, OSError):
            if attempt == retries - 1:
                raise
            time.sleep(backoff)
            backoff = min(backoff * 2.0, 60.0)
    raise RuntimeError("unreachable retry exhausted")


class IsaacusEmbeddingClient:
    def __init__(self, api_key: str, profile: EmbeddingProfile = KANON2_768_V1,
                 timeout: float = 60, transport: Transport = _transport) -> None:
        if not api_key.strip():
            raise ValueError("ISAACUS_API_KEY is required")
        profile.validate()
        self._api_key = api_key
        self.profile = profile
        self.timeout = timeout
        self._transport = transport

    def embed_documents(self, texts: Sequence[str]) -> EmbeddingBatch:
        return self._embed(texts, self.profile.document_task)

    def embed_query(self, query: str) -> tuple[float, ...]:
        return self._embed([query], self.profile.query_task).vectors[0]

    def _embed(self, texts: Sequence[str], task: str) -> EmbeddingBatch:
        values = list(texts)
        if not 1 <= len(values) <= MAX_BATCH_SIZE:
            raise ValueError(f"embedding batch must contain 1 to {MAX_BATCH_SIZE} texts")
        if any(not isinstance(value, str) or not value.strip() for value in values):
            raise ValueError("embedding texts must be non-empty strings")
        payload = {
            "model": self.profile.model, "texts": values, "task": task,
            "overflow_strategy": self.profile.overflow_strategy,
            "dimensions": self.profile.dimensions,
        }
        request = Request(
            API_URL, data=json.dumps(payload, separators=(",", ":")).encode(),
            headers={"Authorization": f"Bearer {self._api_key}",
                     "Content-Type": "application/json", "User-Agent": "FinTaxGPT/0.1"},
            method="POST",
        )
        started = time.perf_counter()
        try:
            response = json.loads(self._transport(request, self.timeout))
            rows = response.get("embeddings")
            if not isinstance(rows, list) or len(rows) != len(values):
                raise ValueError("embedding response count mismatch")
            ordered = sorted(rows, key=lambda row: row.get("index", -1))
            if [row.get("index") for row in ordered] != list(range(len(values))):
                raise ValueError("embedding response indices are invalid")
            vectors = tuple(self._vector(row.get("embedding")) for row in ordered)
            tokens = (response.get("usage") or {}).get("input_tokens")
            if not isinstance(tokens, int) or tokens < 0:
                raise ValueError("embedding response usage is invalid")
            latency_ms = round((time.perf_counter() - started) * 1000, 2)
            record_model_observation(ModelObservation(
                provider="isaacus", model=self.profile.model,
                model_revision=self.profile.profile_id, task=task,
                trace_id=get_current_trace_id() or "", input_tokens=tokens,
                latency_ms=latency_ms,
                cost=calculate_model_cost(self.profile.model, tokens),
            ))
            return EmbeddingBatch(vectors, tokens)
        except Exception as exc:
            latency_ms = round((time.perf_counter() - started) * 1000, 2)
            record_model_observation(ModelObservation(
                provider="isaacus", model=self.profile.model,
                model_revision=self.profile.profile_id, task=task,
                trace_id=get_current_trace_id() or "", status="error",
                latency_ms=latency_ms, metadata={"error": str(exc)},
            ))
            raise

    def _vector(self, value: object) -> tuple[float, ...]:
        if not isinstance(value, list) or len(value) != self.profile.dimensions:
            raise ValueError("embedding response dimension mismatch")
        if any(not isinstance(item, (int, float)) for item in value):
            raise ValueError("embedding response contains a non-numeric value")
        return tuple(float(item) for item in value)
