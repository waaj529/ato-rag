"""Tests for OpenTelemetry and Langfuse-compatible tracing foundation."""

import json
from pathlib import Path
import tempfile

from packages.telemetry import (
    ModelObservation,
    NoOpExporter,
    calculate_model_cost,
    create_telemetry_exporter,
    get_current_case_id,
    get_current_trace_id,
    get_global_collector,
    record_model_observation,
    span,
    trace_context,
)


def test_cost_calculation():
    assert calculate_model_cost("kanon-2-embedder", 1_000_000) == 0.35
    assert calculate_model_cost("kanon-2-reranker", 500_000) == 0.175
    assert calculate_model_cost("unknown-model", 1_000_000) is None


def test_span_hierarchy_and_model_observation():
    collector = get_global_collector()
    collector.clear()

    with trace_context(trace_id="11111111111111111111111111111111", benchmark_case_id="case-42"):
        assert get_current_trace_id() == "11111111111111111111111111111111"
        assert get_current_case_id() == "case-42"

        with span("answer_request") as root:
            with span("query_parse"):
                pass
            with span("retrieval"):
                with span("query_embedding"):
                    obs = ModelObservation(
                        provider="isaacus",
                        model="kanon-2-embedder",
                        model_revision="kanon-2-768-v1",
                        task="query_embedding",
                        trace_id=get_current_trace_id() or "",
                        input_tokens=15,
                        latency_ms=45.2,
                        cost=calculate_model_cost("kanon-2-embedder", 15),
                    )
                    record_model_observation(obs)

    spans = collector.get_spans()
    assert len(spans) == 1
    root_span = spans[0]
    assert root_span.name == "answer_request"
    assert root_span.trace_id == "11111111111111111111111111111111"
    assert len(root_span.children) == 2
    assert root_span.children[0].name == "query_parse"
    assert root_span.children[1].name == "retrieval"
    retrieval_span = root_span.children[1]
    assert len(retrieval_span.children) == 1
    query_embed_span = retrieval_span.children[0]
    assert query_embed_span.name == "query_embedding"
    assert len(query_embed_span.model_observations) == 1

    logged_obs = query_embed_span.model_observations[0]
    assert logged_obs.benchmark_case_id == "case-42"
    assert logged_obs.provider == "isaacus"
    assert logged_obs.model == "kanon-2-embedder"
    assert logged_obs.input_tokens == 15
    assert logged_obs.cost > 0

    otlp = collector.export_otlp_json()
    assert "resourceSpans" in otlp
    assert len(otlp["resourceSpans"][0]["scopeSpans"][0]["spans"]) == 5

    with tempfile.TemporaryDirectory() as tmpdir:
        jsonl_path = Path(tmpdir) / "traces.jsonl"
        collector.export_jsonl(jsonl_path)
        assert jsonl_path.exists()
        lines = jsonl_path.read_text().strip().split("\n")
        assert len(lines) == 1
        data = json.loads(lines[0])
        assert data["trace_id"] == "11111111111111111111111111111111"
        assert data["benchmark_case_id"] == "case-42"


def test_noop_exporter_and_telemetry_factory(monkeypatch):
    monkeypatch.delenv("LANGFUSE_HOST", raising=False)
    monkeypatch.delenv("FINTAX_TELEMETRY_EXPORTER", raising=False)

    exporter = create_telemetry_exporter(allow_noop=True)
    assert isinstance(exporter, NoOpExporter)
    exporter.export([])
    exporter.client.close()
    exporter.close()

    monkeypatch.setenv("FINTAX_TELEMETRY_EXPORTER", "noop")
    assert isinstance(create_telemetry_exporter(), NoOpExporter)
