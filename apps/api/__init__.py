"""Explicitly configured staging application factory; no anonymous or mock fallback."""

from contextlib import asynccontextmanager
import os

from packages.security.oidc import OIDCAuthenticator
from packages.telemetry import create_telemetry_exporter
from services.answering import AnswerService, create_pool
from services.generation import ProductionGenerator, GenerationSettings
from .application import create_app


def production_app():
    settings = GenerationSettings.from_env()
    auth, exporter = OIDCAuthenticator.from_env(), create_telemetry_exporter()
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

    return create_app(auth, AnswerService(pool, key, generator), exporter, lifespan=lifespan)


__all__ = ["create_app", "production_app"]
