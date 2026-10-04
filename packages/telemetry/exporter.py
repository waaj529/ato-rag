"""Authenticated bounded OTLP delivery; errors never include secrets or payloads."""

import base64
import os
from urllib.parse import urlsplit

import httpx

from .otlp import encode_otlp


class TelemetryExportError(RuntimeError):
    pass


class NoOpExporter:
    """Null telemetry sink for local execution, tests, and deferred tracing."""

    def __init__(self):
        class _Client:
            def close(self):
                pass
        self.client = _Client()

    def export(self, roots):
        pass

    def close(self):
        pass


def create_telemetry_exporter(allow_noop: bool = True):
    mode = os.environ.get("FINTAX_TELEMETRY_EXPORTER", "").lower()
    if mode == "noop" or (allow_noop and not os.environ.get("LANGFUSE_HOST")):
        return NoOpExporter()
    return LangfuseExporter.from_env()


class LangfuseExporter:
    def __init__(self, host: str, public_key: str, secret_key: str, client=None):
        parsed = urlsplit(host)
        if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.query or parsed.fragment:
            raise ValueError("Langfuse host must be HTTPS without credentials or query")
        if not public_key or not secret_key:
            raise ValueError("Langfuse project credentials required")
        self.endpoint = host.rstrip("/") + "/api/public/otel/v1/traces"
        self._authorization = "Basic " + base64.b64encode(f"{public_key}:{secret_key}".encode()).decode()
        self.client = client or httpx.Client(timeout=10, follow_redirects=False)

    @classmethod
    def from_env(cls):
        values = [os.environ.get(key, "") for key in
                  ("LANGFUSE_HOST", "LANGFUSE_PUBLIC_KEY", "LANGFUSE_SECRET_KEY")]
        if not all(values):
            raise ValueError("Langfuse host and project credentials are required")
        return cls(*values)

    def export(self, roots):
        payload = encode_otlp(roots)
        try:
            response = self.client.post(self.endpoint, json=payload, headers={
                "Authorization": self._authorization, "x-langfuse-ingestion-version": "4",
            })
            if response.status_code != 200:
                raise TelemetryExportError(f"OTLP export rejected: HTTP {response.status_code}")
            result = response.json() if response.content else {}
            partial = result.get("partialSuccess", {})
            if int(partial.get("rejectedSpans", 0)) or partial.get("errorMessage"):
                raise TelemetryExportError("OTLP export reported partial failure")
        except TelemetryExportError:
            raise
        except Exception:
            raise TelemetryExportError("OTLP delivery failed") from None
