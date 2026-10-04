"""Signed authentication, scope enforcement and required telemetry at the HTTP boundary."""

from concurrent.futures import ThreadPoolExecutor
from types import SimpleNamespace
import time

from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi.testclient import TestClient
import jwt
import pytest

from apps.api import create_app
from packages.security.oidc import OIDCAuthenticator
from packages.telemetry import TelemetryExportError


@pytest.fixture
def api():
    private = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    keys = SimpleNamespace(get_signing_key_from_jwt=lambda token: SimpleNamespace(key=private.public_key()))
    auth = OIDCAuthenticator("https://issuer.example", "fintax", "https://issuer.example/jwks", keys)
    seen, traces = [], []
    def execute(body, scope, answer):
        seen.append((scope, body.matter_id, answer))
        return {"ok": True}
    exporter = SimpleNamespace(export=lambda roots: traces.extend(roots))
    app = create_app(auth, SimpleNamespace(execute=execute), exporter)
    def token(**overrides):
        payload = {"iss": "https://issuer.example", "aud": "fintax", "sub": "user-1", "tid": "tenant-1",
                   "iat": int(time.time()), "exp": int(time.time())+300, "matter_ids": ["matter-1"]}
        payload.update(overrides)
        return jwt.encode(payload, private, algorithm="RS256")
    return TestClient(app), token, seen, traces, exporter


@pytest.mark.parametrize("token", [None, '{"sub":"admin","tid":"victim"}', "admin:victim:admin"])
def test_unsigned_and_missing_tokens_are_rejected(api, token):
    client, _, seen, _, _ = api
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    assert client.post("/v1/answer", json={"query": "tax"}, headers=headers).status_code == 401
    assert seen == []


@pytest.mark.parametrize("override", [{"aud": "other"}, {"iss": "https://other.example"}, {"exp": 1}])
def test_wrong_audience_issuer_and_expired_tokens_fail(api, override):
    client, token, seen, _, _ = api
    assert client.post("/v1/answer", json={"query": "tax"}, headers={"Authorization": f"Bearer {token(**override)}"}).status_code == 401
    assert seen == []


def test_scope_comes_from_verified_identity_not_request_body(api):
    client, token, seen, traces, _ = api
    headers = {"Authorization": f"Bearer {token()}"}
    assert client.post("/v1/answer", json={"query": "tax", "tenant_id": "victim"}, headers=headers).status_code == 422
    assert client.post("/v1/answer", json={"query": "tax", "matter_id": "other"}, headers=headers).status_code == 403
    result = client.post("/v1/retrieve", json={"query": "tax", "matter_id": "matter-1"}, headers=headers)
    assert result.status_code == 200
    assert seen[0][0].tenant_id == "tenant-1"
    assert seen[0][1:] == ("matter-1", False)
    assert result.json()["trace_id"] == traces[0].trace_id
    assert result.headers["cache-control"].startswith("no-store")


def test_export_failure_blocks_success_response(api):
    client, token, _, _, exporter = api
    def fail(roots):
        raise TelemetryExportError("unavailable")
    exporter.export = fail
    response = client.post("/v1/answer", json={"query": "tax"}, headers={"Authorization": f"Bearer {token()}"})
    assert response.status_code == 503
    assert "trace" not in response.text


def test_concurrent_api_requests_preserve_distinct_tenants_and_trace_ids(api):
    client, token, seen, traces, _ = api
    def request(index):
        return client.post("/v1/retrieve", json={"query": "tax"},
                           headers={"Authorization": f"Bearer {token(tid=f'tenant-{index}')}"})
    with ThreadPoolExecutor(max_workers=8) as workers:
        responses = list(workers.map(request, range(20)))
    assert all(r.status_code == 200 for r in responses)
    assert len({r.json()["trace_id"] for r in responses}) == 20
    assert len({s[0].tenant_id for s in seen}) == 20
