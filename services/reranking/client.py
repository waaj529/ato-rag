"""Strict Isaacus Kanon 2 reranking API adapter."""

from dataclasses import dataclass
import json
import time
from typing import Callable, Sequence
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


API_URL = "https://api.isaacus.com/v1/rerankings"
Transport = Callable[[Request, float], bytes]


@dataclass(frozen=True)
class RerankingBatch:
    results: tuple[tuple[int, float], ...]
    input_tokens: int


def _transport(request: Request, timeout: float) -> bytes:
    backoff = 2.0
    for attempt in range(8):
        try:
            with urlopen(request, timeout=timeout) as response:
                return response.read()
        except HTTPError as error:
            body = error.read().decode("utf-8", errors="replace")
            if error.code not in {429, 500, 502, 503, 504} or attempt == 7:
                raise ValueError(f"Isaacus API HTTP {error.code}: {body}") from error
        except (URLError, TimeoutError, ConnectionError, OSError):
            if attempt == 7:
                raise
        time.sleep(backoff)
        backoff = min(backoff * 2.0, 60.0)
    raise RuntimeError("unreachable retry exhausted")


class IsaacusRerankingClient:
    def __init__(self, api_key: str, model: str = "kanon-2-reranker",
                 timeout: float = 60, transport: Transport = _transport) -> None:
        if not api_key.strip():
            raise ValueError("ISAACUS_API_KEY is required")
        self._api_key = api_key
        self.model = model
        self.timeout = timeout
        self._transport = transport

    def rerank(self, query: str, texts: Sequence[str], top_n: int) -> RerankingBatch:
        values = list(texts)
        if not query.strip():
            raise ValueError("reranking query must not be empty")
        if not values or any(not isinstance(value, str) or not value.strip() for value in values):
            raise ValueError("reranking texts must be non-empty strings")
        if not 1 <= top_n <= len(values):
            raise ValueError("top_n must be within the supplied text count")
        payload = {"model": self.model, "query": query, "texts": values, "top_n": top_n}
        request = Request(
            API_URL, data=json.dumps(payload, separators=(",", ":")).encode(),
            headers={"Authorization": f"Bearer {self._api_key}",
                     "Content-Type": "application/json", "User-Agent": "FinTaxGPT/0.1"},
            method="POST",
        )
        response = json.loads(self._transport(request, self.timeout))
        rows = response.get("results")
        if not isinstance(rows, list) or len(rows) != top_n:
            raise ValueError("reranking response count mismatch")
        results = tuple(self._result(row, len(values)) for row in rows)
        if len({index for index, _ in results}) != len(results):
            raise ValueError("reranking response contains duplicate indices")
        tokens = (response.get("usage") or {}).get("input_tokens")
        if not isinstance(tokens, int) or tokens < 0:
            raise ValueError("reranking response usage is invalid")
        return RerankingBatch(results, tokens)

    @staticmethod
    def _result(row: object, count: int) -> tuple[int, float]:
        if not isinstance(row, dict):
            raise ValueError("reranking result is invalid")
        index, score = row.get("index"), row.get("score")
        if not isinstance(index, int) or not 0 <= index < count:
            raise ValueError("reranking result index is invalid")
        if not isinstance(score, (int, float)) or not 0 <= float(score) <= 1:
            raise ValueError("reranking result score is invalid")
        return index, float(score)
