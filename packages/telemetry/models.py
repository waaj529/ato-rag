"""Typed OpenTelemetry and Langfuse-compatible trace models."""

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
import uuid


def generate_trace_id() -> str:
    return uuid.uuid4().hex


def generate_span_id() -> str:
    return uuid.uuid4().hex[:16]


@dataclass
class ModelObservation:
    provider: str
    model: str
    model_revision: str
    task: str
    trace_id: str
    observation_id: str = field(default_factory=generate_span_id)
    parent_observation_id: str | None = None
    benchmark_case_id: str | None = None
    corpus_revision: str | None = None
    retrieval_config_version: str | None = None
    reranker_config_version: str | None = None
    input_tokens: int = 0
    output_tokens: int = 0
    latency_ms: float = 0.0
    cost: float | None = 0.0
    cache_hit: bool = False
    retry_count: int = 0
    status: str = "ok"
    provider_request_id: str | None = None
    metadata: dict[str, object] = field(default_factory=dict)
    created_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class SpanRecord:
    trace_id: str
    span_id: str
    name: str
    parent_span_id: str | None = None
    start_time_ns: int = 0
    end_time_ns: int | None = None
    status: str = "ok"
    attributes: dict[str, object] = field(default_factory=dict)
    model_observations: list[ModelObservation] = field(default_factory=list)
    children: list["SpanRecord"] = field(default_factory=list)

    @property
    def latency_ms(self) -> float:
        if self.end_time_ns is None:
            return 0.0
        return (self.end_time_ns - self.start_time_ns) / 1_000_000.0

    def to_dict(self) -> dict:
        return {
            "trace_id": self.trace_id,
            "span_id": self.span_id,
            "name": self.name,
            "parent_span_id": self.parent_span_id,
            "start_time_ns": self.start_time_ns,
            "end_time_ns": self.end_time_ns,
            "latency_ms": self.latency_ms,
            "status": self.status,
            "attributes": dict(self.attributes),
            "model_observations": [m.to_dict() for m in self.model_observations],
            "children": [c.to_dict() for c in self.children],
        }
