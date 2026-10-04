"""OTLP/HTTP JSON encoding with metadata allowlisting and real model child spans."""

import json
import re

from .models import SpanRecord

_SAFE = frozenset({"settings_version", "version", "error.type", "evaluation.kind"})


def _value(value):
    if isinstance(value, bool):
        return {"boolValue": value}
    if isinstance(value, int):
        return {"intValue": str(value)}
    if isinstance(value, float):
        return {"doubleValue": value}
    return {"stringValue": str(value)}


def _span(record, attributes):
    if not re.fullmatch(r"[0-9a-f]{32}", record.trace_id) or int(record.trace_id, 16) == 0:
        raise ValueError("OTLP requires nonzero 32-character hex trace IDs")
    return {
        "traceId": record.trace_id, "spanId": record.span_id,
        "parentSpanId": record.parent_span_id or "", "name": record.name, "kind": 1,
        "startTimeUnixNano": str(record.start_time_ns),
        "endTimeUnixNano": str(record.end_time_ns or record.start_time_ns),
        "attributes": [{"key": k, "value": _value(v)} for k, v in attributes.items()],
        "status": {"code": 1 if record.status == "ok" else 2},
    }


def encode_otlp(roots: list[SpanRecord]) -> dict:
    spans = []

    def append(record):
        spans.append(_span(record, {k: v for k, v in record.attributes.items() if k in _SAFE}))
        for obs in record.model_observations:
            attrs = {
                "langfuse.observation.type": ("span" if obs.metadata.get("provider_request_sent") is False
                                              else "embedding" if "embed" in obs.task else "generation"),
                "gen_ai.system": obs.provider, "gen_ai.response.model": obs.model,
                "gen_ai.operation.name": obs.task, "langfuse.version": obs.model_revision,
                "langfuse.observation.usage_details": json.dumps({
                    "input": obs.input_tokens, "output": obs.output_tokens,
                }),
                "langfuse.observation.metadata.usage_status": obs.metadata.get("usage_status", "recorded"),
                "langfuse.observation.metadata.cost_basis": obs.metadata.get("cost_basis", "legacy_estimate"),
            }
            if obs.cost is not None:
                attrs["langfuse.observation.cost_details"] = json.dumps({"total": obs.cost})
            end = record.end_time_ns or record.start_time_ns
            model_span = SpanRecord(
                record.trace_id, obs.observation_id, obs.task, record.span_id,
                max(record.start_time_ns, end-int(obs.latency_ms*1_000_000)), end, obs.status,
            )
            spans.append(_span(model_span, attrs))
        for child in record.children:
            append(child)

    for root in roots:
        append(root)
    return {"resourceSpans": [{
        "resource": {"attributes": [{"key": "service.name", "value": {"stringValue": "fintaxgpt"}}]},
        "scopeSpans": [{"scope": {"name": "fintaxgpt", "version": "0.2"}, "spans": spans}],
    }]}
