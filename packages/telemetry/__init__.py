"""OpenTelemetry and Langfuse-compatible tracing foundation."""

from .collector import TraceCollector, get_global_collector, collect_request
from .exporter import (
    LangfuseExporter,
    NoOpExporter,
    TelemetryExportError,
    create_telemetry_exporter,
)
from .cost import calculate_model_cost
from .context import (
    get_current_case_id,
    get_current_span,
    get_current_trace_id,
    record_model_observation,
    span,
    trace_context,
)
from .models import (
    ModelObservation,
    SpanRecord,
    generate_span_id,
    generate_trace_id,
)

__all__ = [
    "collect_request",
    "create_telemetry_exporter",
    "LangfuseExporter",
    "NoOpExporter",
    "TelemetryExportError",
    "ModelObservation",
    "SpanRecord",
    "TraceCollector",
    "calculate_model_cost",
    "generate_span_id",
    "generate_trace_id",
    "get_current_case_id",
    "get_current_span",
    "get_current_trace_id",
    "get_global_collector",
    "record_model_observation",
    "span",
    "trace_context",
]
