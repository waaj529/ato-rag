"""Authenticated answer/retrieval HTTP boundary with request-local traces."""

from threading import Lock

from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel, ConfigDict, Field

from packages.security import PermissionDeniedError, RateLimiter, RateLimitExceededError, enforce_request_scope
from packages.security.headers import get_security_headers
from packages.telemetry import collect_request, span, trace_context, TelemetryExportError
from services.generation import ProviderError


class QueryRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    query: str = Field(min_length=1, max_length=8000)
    matter_id: str | None = Field(default=None, max_length=200)


def create_app(authenticator, service, exporter, lifespan=None, service_authenticator=None):
    app = FastAPI(title="FinTaxGPT staging API", lifespan=lifespan)
    limiter, lock = RateLimiter(max_requests=30), Lock()

    @app.middleware("http")
    async def security_headers(request, call_next):
        response = await call_next(request)
        response.headers.update(get_security_headers())
        return response

    def execute(body, authorization, answer):
        if not authorization or not authorization.startswith("Bearer "):
            raise HTTPException(401, "Bearer access token required", headers={"WWW-Authenticate": "Bearer"})
        scope = service_authenticator.authenticate(authorization) if service_authenticator else None
        if scope is None and authenticator is None:
            raise HTTPException(401, "Invalid access token")
        if scope is None:
            try:
                scope = authenticator.authenticate(authorization[7:])
            except ValueError:
                raise HTTPException(401, "Invalid access token") from None
        try:
            enforce_request_scope(scope, matter_id=body.matter_id)
            with lock:
                limiter.acquire(scope.tenant_id)
        except PermissionDeniedError:
            raise HTTPException(403, "Scope does not permit this request") from None
        except RateLimitExceededError:
            raise HTTPException(429, "Request rate exceeded") from None
        try:
            with collect_request() as collector, trace_context() as trace_id:
                try:
                    with span("answer_request" if answer else "retrieve_request"):
                        result = service.execute(body, scope, answer=answer)
                finally:
                    exporter.export(collector.get_spans())
                return {"trace_id": trace_id, **result}
        except PermissionDeniedError:
            raise HTTPException(403, "Matter is not accessible") from None
        except (ProviderError, TelemetryExportError):
            raise HTTPException(503, "Required provider unavailable") from None
        except Exception:
            raise HTTPException(503, "Request could not be completed") from None

    @app.post("/v1/answer")
    def answer(body: QueryRequest, authorization: str | None = Header(default=None)):
        return execute(body, authorization, True)

    @app.post("/v1/retrieve")
    def retrieve(body: QueryRequest, authorization: str | None = Header(default=None)):
        return execute(body, authorization, False)

    return app
