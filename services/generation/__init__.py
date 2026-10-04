"""Bounded generation, structured claims and model routing (Phase 5)."""

from .adapters import ExtractiveGenerator, RepairGenerator
from .base import GenerationAdapter
from .models import Claim, StructuredAnswer, format_generation_prompt
from .router import ModelRouter
from .provider import ProductionGenerator, ProviderError
from .settings import GenerationSettings

__all__ = [
    "ProductionGenerator",
    "ProviderError",
    "GenerationSettings",
    "Claim",
    "GenerationAdapter",
    "ExtractiveGenerator",
    "ModelRouter",
    "RepairGenerator",
    "StructuredAnswer",
    "format_generation_prompt",
]
