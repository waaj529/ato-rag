"""Provider wire-contract, honest usage and failure-path regression tests."""

import json

import httpx
import pytest

from packages.telemetry import collect_request, span, trace_context
from services.context_builder import ContextPackage
from services.generation import GenerationSettings, ModelRouter, ProductionGenerator, ProviderError


def _body():
    return {"model": "provider-model-snapshot", "usage": {"prompt_tokens": 100, "completion_tokens": 20},
            "choices": [{"finish_reason": "stop", "message": {"content": json.dumps({
                "claims": [{"claim_id": "C1", "text": "Deduction is conditional.", "evidence_ids": ["E1"]}],
                "limitations": [], "needs_human_review": True,
            })}}]}


def _settings(**kwargs):
    return GenerationSettings("https://provider.example/v1/chat/completions", "secret", "configured-provider",
                              "pinned-model", "revision-1", **kwargs)


def _context():
    return ContextPackage("deductions", (), 0, "test")


def test_real_adapter_posts_structured_request_and_records_usage():
    def transport(request):
        body = json.loads(request.content)
        assert request.headers["authorization"] == "Bearer secret"
        assert body["response_format"]["json_schema"]["strict"] is True
        assert body["store"] is False
        assert body["messages"][0]["role"] == "system"
        return httpx.Response(200, json=_body(), headers={"x-request-id": "request-1"})

    adapter = ProductionGenerator(_settings(input_rate=2, output_rate=8),
                                  httpx.Client(transport=httpx.MockTransport(transport)))
    with collect_request() as collector, trace_context(), span("request"):
        answer = ModelRouter(adapter).generate("deductions", _context())
    assert answer.claims[0].evidence_ids == ("E1",)
    assert answer.answer_markdown == "Deduction is conditional. [E1]"
    obs = collector.get_observations()[0]
    assert (obs.input_tokens, obs.output_tokens) == (100, 20)
    assert obs.model == "provider-model-snapshot"
    assert obs.provider_request_id == "request-1"
    assert obs.cost == pytest.approx(0.00036)
    assert obs.metadata["cost_basis"] == "configured_rate_estimate"


@pytest.mark.parametrize("mode", ["http", "truncated", "refusal", "malformed", "usage", "extra_prose"])
def test_invalid_provider_result_never_returns_an_answer(mode):
    body = _body()
    if mode == "truncated":
        body["choices"][0]["finish_reason"] = "length"
    elif mode == "refusal":
        body["choices"][0]["message"]["refusal"] = "private detail"
    elif mode == "malformed":
        body["choices"][0]["message"]["content"] = "not json"
    elif mode == "usage":
        body["usage"]["prompt_tokens"] = -1
    elif mode == "extra_prose":
        result = json.loads(body["choices"][0]["message"]["content"])
        result["answer_markdown"] = "uncited advice"
        body["choices"][0]["message"]["content"] = json.dumps(result)
    client = httpx.Client(transport=httpx.MockTransport(lambda r: httpx.Response(500 if mode == "http" else 200, json=body)))
    with collect_request() as collector, trace_context():
        with pytest.raises(ProviderError) as err:
            ProductionGenerator(_settings(), client).generate_answer("private query", _context())
    assert "private" not in str(err.value)
    obs = collector.get_observations()[0]
    assert obs.status == "error"
    assert obs.cost is None


def test_default_cannot_silently_fall_back_to_extractive_output(monkeypatch):
    monkeypatch.delenv("FINTAX_LLM_ENDPOINT", raising=False)
    with pytest.raises(ValueError, match="FINTAX_LLM_ENDPOINT"):
        ModelRouter().generate("deductions", _context())


def test_repair_is_an_actual_separately_traced_provider_call():
    adapter = ProductionGenerator(_settings(), httpx.Client(transport=httpx.MockTransport(lambda r: httpx.Response(200, json=_body()))))
    with collect_request() as collector, trace_context():
        router = ModelRouter(adapter)
        draft = router.generate("q", _context())
        router.repair(draft, ("invalid citation",), _context())
    assert [o.task for o in collector.get_observations()] == ["generate", "repair"]
    assert all(o.cost is None for o in collector.get_observations())


def test_provider_outage_opens_circuit_without_additional_network_calls():
    calls = []
    def unavailable(request):
        calls.append(request)
        return httpx.Response(503, json={})
    generator = ProductionGenerator(_settings(), httpx.Client(transport=httpx.MockTransport(unavailable)))
    with collect_request() as collector, trace_context():
        for _ in range(5):
            with pytest.raises(ProviderError):
                generator.generate_answer("tax", _context())
    assert len(calls) == 3
    assert len(collector.get_observations()) == 5
    assert all(o.status == "error" for o in collector.get_observations())
