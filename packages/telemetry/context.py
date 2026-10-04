"""Context variables and span lifecycle management."""

from contextlib import contextmanager
from contextvars import ContextVar
import time
from typing import Any, Iterator

from .collector import get_global_collector
from .models import ModelObservation, SpanRecord, generate_span_id, generate_trace_id

_ACTIVE_SPAN: ContextVar[SpanRecord | None] = ContextVar("_ACTIVE_SPAN", default=None)
_ROOT_SPAN: ContextVar[SpanRecord | None] = ContextVar("_ROOT_SPAN", default=None)
_ACTIVE_TRACE_ID: ContextVar[str | None] = ContextVar("_ACTIVE_TRACE_ID", default=None)
_CASE_ID: ContextVar[str | None] = ContextVar("_CASE_ID", default=None)
_CORPUS_REV: ContextVar[str | None] = ContextVar("_CORPUS_REV", default="2026-09-26")
_RETRIEVAL_VER: ContextVar[str | None] = ContextVar("_RETRIEVAL_VER", default=None)
_RERANKER_VER: ContextVar[str | None] = ContextVar("_RERANKER_VER", default=None)


def get_current_trace_id() -> str | None:
    return _ACTIVE_TRACE_ID.get()


def get_current_span() -> SpanRecord | None:
    return _ACTIVE_SPAN.get()


def get_current_case_id() -> str | None:
    return _CASE_ID.get()


@contextmanager
def trace_context(
    trace_id: str | None = None,
    benchmark_case_id: str | None = None,
    corpus_revision: str | None = None,
    retrieval_config_version: str | None = None,
    reranker_config_version: str | None = None,
    exporter: Any | None = None,
) -> Iterator[str]:
    tid = trace_id or generate_trace_id()
    t_token = _ACTIVE_TRACE_ID.set(tid)
    c_token = _CASE_ID.set(benchmark_case_id)
    cr_token = _CORPUS_REV.set(corpus_revision or _CORPUS_REV.get())
    rcv_token = _RETRIEVAL_VER.set(retrieval_config_version)
    rrv_token = _RERANKER_VER.set(reranker_config_version)
    try:
        yield tid
    finally:
        _ACTIVE_TRACE_ID.reset(t_token)
        _CASE_ID.reset(c_token)
        _CORPUS_REV.reset(cr_token)
        _RETRIEVAL_VER.reset(rcv_token)
        _RERANKER_VER.reset(rrv_token)
        if exporter is not None:
            exporter.export([root for root in get_global_collector().get_spans() if root.trace_id == tid])


@contextmanager
def span(name: str, attributes: dict[str, Any] | None = None) -> Iterator[SpanRecord]:
    parent = _ACTIVE_SPAN.get()
    trace_id = _ACTIVE_TRACE_ID.get() or (parent.trace_id if parent else generate_trace_id())
    current = SpanRecord(
        trace_id=trace_id,
        span_id=generate_span_id(),
        name=name,
        parent_span_id=parent.span_id if parent else None,
        start_time_ns=time.time_ns(),
        attributes=dict(attributes or {}),
    )
    if parent:
        parent.children.append(current)
    else:
        _ROOT_SPAN.set(current)
    span_token = _ACTIVE_SPAN.set(current)
    try:
        yield current
    except Exception as exc:
        current.status = "error"
        current.attributes["error.type"] = type(exc).__name__
        raise
    finally:
        current.end_time_ns = time.time_ns()
        _ACTIVE_SPAN.reset(span_token)
        if parent is None:
            get_global_collector().record_root_span(current)


def record_model_observation(observation: ModelObservation) -> None:
    if not observation.trace_id and _ACTIVE_TRACE_ID.get():
        observation.trace_id = _ACTIVE_TRACE_ID.get() or ""
    if not observation.benchmark_case_id:
        observation.benchmark_case_id = _CASE_ID.get()
    if not observation.corpus_revision:
        observation.corpus_revision = _CORPUS_REV.get()
    if not observation.retrieval_config_version:
        observation.retrieval_config_version = _RETRIEVAL_VER.get()
    if not observation.reranker_config_version:
        observation.reranker_config_version = _RERANKER_VER.get()
    current_span = _ACTIVE_SPAN.get()
    if current_span:
        observation.trace_id = current_span.trace_id
        if not observation.parent_observation_id:
            observation.parent_observation_id = current_span.span_id
        current_span.model_observations.append(observation)
    get_global_collector().record_observation(observation)
