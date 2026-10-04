"""Collector and exporter for OpenTelemetry and Langfuse-compatible traces."""

import json
from pathlib import Path
from typing import TYPE_CHECKING
from contextvars import ContextVar
from contextlib import contextmanager

if TYPE_CHECKING:
    from .models import ModelObservation, SpanRecord


class TraceCollector:
    def __init__(self) -> None:
        self.spans: list["SpanRecord"] = []
        self.observations: list["ModelObservation"] = []

    def record_root_span(self, root_span: "SpanRecord") -> None:
        self.spans.append(root_span)

    def record_observation(self, observation: "ModelObservation") -> None:
        self.observations.append(observation)

    def clear(self) -> None:
        self.spans.clear()
        self.observations.clear()

    def get_spans(self) -> list["SpanRecord"]:
        return list(self.spans)

    def get_observations(self) -> list["ModelObservation"]:
        return list(self.observations)

    def export_otlp_json(self) -> dict:
        """Encode validated OTLP, including actual model observations and redaction."""
        from .otlp import encode_otlp
        return encode_otlp(self.spans)

    def export_jsonl(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as handle:
            for obs in self.observations:
                handle.write(json.dumps(obs.to_dict()) + "\n")


_COLLECTOR = TraceCollector()


_REQUEST_COLLECTOR: ContextVar[TraceCollector | None] = ContextVar("request_collector", default=None)


def get_global_collector() -> TraceCollector:
    return _REQUEST_COLLECTOR.get() or _COLLECTOR


@contextmanager
def collect_request():
    collector = TraceCollector()
    token = _REQUEST_COLLECTOR.set(collector)
    try:
        yield collector
    finally:
        _REQUEST_COLLECTOR.reset(token)
