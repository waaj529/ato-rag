"""Authenticated HTTP delivery, private payload exclusion and request trace isolation."""

from concurrent.futures import ThreadPoolExecutor
import json
import time

import httpx
import pytest

from packages.telemetry import (
    LangfuseExporter, ModelObservation, TelemetryExportError, collect_request,
    record_model_observation, span, trace_context,
)


def _traces():
    with collect_request() as collector, trace_context():
        with span("request", {"query": "TFN secret", "tenant_id": "private tenant"}):
            with span("generation"):
                record_model_observation(ModelObservation("provider", "model", "revision", "generate", "",
                                         input_tokens=30, cost=None, metadata={"error": "secret-key"}))
    return collector.get_spans()


def test_otlp_posts_model_children_with_epoch_timestamps_and_no_private_payloads():
    roots = _traces()
    captured = []
    def receive(request):
        captured.append(request)
        return httpx.Response(200, json={})
    exporter = LangfuseExporter("https://langfuse.example", "public", "secret",
                               httpx.Client(transport=httpx.MockTransport(receive)))
    exporter.export(roots)
    request = captured[0]
    assert request.url.path == "/api/public/otel/v1/traces"
    assert request.headers["authorization"].startswith("Basic ")
    raw = request.content.decode()
    assert all(private not in raw for private in ("TFN", "private tenant", "secret-key"))
    spans = json.loads(raw)["resourceSpans"][0]["scopeSpans"][0]["spans"]
    assert len(spans) == 3
    assert len({s["traceId"] for s in spans}) == 1
    assert all(int(s["startTimeUnixNano"]) > time.time_ns()-60_000_000_000 for s in spans)
    model = spans[2]
    assert model["parentSpanId"] == spans[1]["spanId"]
    assert any(a["key"] == "gen_ai.response.model" for a in model["attributes"])
    assert not any(a["key"] == "langfuse.observation.cost_details" for a in model["attributes"])


@pytest.mark.parametrize("status,body", [(401, {}), (503, {}), (200, {"partialSuccess": {"rejectedSpans": "1"}})])
def test_exporter_rejection_is_not_reported_as_success(status, body):
    exporter = LangfuseExporter("https://langfuse.example", "public", "secret",
                               httpx.Client(transport=httpx.MockTransport(lambda r: httpx.Response(status, json=body))))
    with pytest.raises(TelemetryExportError):
        exporter.export(_traces())


def test_concurrent_request_collectors_do_not_mix_traces():
    with ThreadPoolExecutor(max_workers=8) as workers:
        results = list(workers.map(lambda _: _traces(), range(40)))
    assert all(len(roots) == 1 for roots in results)
    assert len({roots[0].trace_id for roots in results}) == 40


def test_benchmark_trace_exports_even_when_provider_operation_fails():
    sent = []
    class Exporter:
        def export(self, roots):
            sent.extend(roots)
    with collect_request(), pytest.raises(RuntimeError):
        with trace_context(exporter=Exporter()), span("failed-provider-call"):
            raise RuntimeError("private error body")
    assert len(sent) == 1
    assert sent[0].status == "error"
    assert "private error body" not in str(sent[0].attributes)
