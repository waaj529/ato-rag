"""Explicit production generation configuration; no implicit provider or pricing."""

from dataclasses import dataclass, field
import math
import os
from urllib.parse import urlsplit


@dataclass(frozen=True)
class GenerationSettings:
    endpoint: str
    api_key: str = field(repr=False)
    provider: str
    model: str
    revision: str
    input_rate: float | None = None
    output_rate: float | None = None
    cached_input_rate: float | None = None
    timeout: float = 45.0
    max_output_tokens: int = 3000

    def __post_init__(self):
        url = urlsplit(self.endpoint)
        if url.scheme != "https" or not url.hostname or url.username or url.query or url.fragment:
            raise ValueError("Generation endpoint must be an HTTPS URL without credentials or query")
        if not all(x.strip() for x in (self.api_key, self.provider, self.model, self.revision)):
            raise ValueError("Generation provider, key, pinned model and revision are required")
        for rate in (self.input_rate, self.output_rate, self.cached_input_rate):
            if rate is not None and (not math.isfinite(rate) or rate < 0):
                raise ValueError("Token prices must be finite and non-negative")
        if not 0 < self.timeout <= 120 or not 0 < self.max_output_tokens <= 16000:
            raise ValueError("Invalid generation timeout or token limit")

    @classmethod
    def from_env(cls):
        def required(name):
            value = os.environ.get(f"FINTAX_LLM_{name}", "").strip()
            if not value:
                raise ValueError(f"Missing FINTAX_LLM_{name}; production generation is not configured")
            return value

        def rate(name):
            value = os.environ.get(f"FINTAX_LLM_{name}")
            return float(value) if value is not None else None

        return cls(required("ENDPOINT"), required("API_KEY"), required("PROVIDER"),
                   required("MODEL"), required("REVISION"), rate("INPUT_RATE"),
                   rate("OUTPUT_RATE"), rate("CACHED_INPUT_RATE"))
