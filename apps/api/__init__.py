"""Explicitly configured staging application factory; no anonymous or mock fallback."""

from contextlib import asynccontextmanager
import os

from packages.security.oidc import OIDCAuthenticator
from packages.telemetry import create_telemetry_exporter
from services.answering import AnswerService, create_pool
from services.generation import ProductionGenerator, GenerationSettings
from .application import create_app
from .service_auth import ServiceTokenAuthenticator


def production_app():
    settings = GenerationSettings.from_env()
    service_auth = ServiceTokenAuthenticator.from_env()
    oidc_keys = ("FINTAX_OIDC_ISSUER", "FINTAX_OIDC_AUDIENCE", "FINTAX_OIDC_JWKS_URL")
    auth = OIDCAuthenticator.from_env() if any(os.environ.get(key) for key in oidc_keys) else None
    if auth is None and service_auth is None:
        raise ValueError("Configure OIDC or FINTAX_CHAT_SERVICE_API_KEY")
    exporter = create_telemetry_exporter()
    dsn, key = os.environ.get("FINTAX_DATABASE_URL"), os.environ.get("ISAACUS_API_KEY")
    if not dsn or not key:
        raise ValueError("FINTAX_DATABASE_URL and ISAACUS_API_KEY are required")
    pool = create_pool(dsn)
    generator = ProductionGenerator(settings)

    @asynccontextmanager
    async def lifespan(app):
        pool.open()
        try:
            pool.wait(timeout=15)
            yield
        finally:
            pool.close()
            generator.client.close()
            exporter.client.close()

    return create_app(
        auth,
        AnswerService(pool, key, generator),
        exporter,
        lifespan=lifespan,
        service_authenticator=service_auth,
    )


__all__ = ["create_app", "production_app"]
