"""Production generation routing; extractive fixtures require explicit injection."""

from services.context_builder import ContextPackage
from .adapters import RepairGenerator
from .base import GenerationAdapter
from .models import StructuredAnswer
from .provider import ProductionGenerator
from .settings import GenerationSettings


class ModelRouter:
    def __init__(self, default_generator: GenerationAdapter | None = None,
                 repair_generator: RepairGenerator | None = None) -> None:
        self.generator = default_generator
        self.repairer = repair_generator

    def _configured(self):
        if self.generator is None:
            self.generator = ProductionGenerator(GenerationSettings.from_env())
        return self.generator

    def generate(self, query: str, context: ContextPackage) -> StructuredAnswer:
        answer, _, _ = self._configured().generate_answer(query, context, task="generate")
        return answer

    def repair(self, draft: StructuredAnswer, errors: tuple[str, ...], context: ContextPackage):
        generator = self._configured()
        if isinstance(generator, ProductionGenerator):
            return generator.repair(draft, errors, context)
        return (self.repairer or RepairGenerator()).repair(draft, errors, context)
