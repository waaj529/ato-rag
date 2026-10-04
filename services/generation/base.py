"""Provider-neutral generation adapter protocol."""

from typing import Protocol

from services.context_builder import ContextPackage
from .models import StructuredAnswer


class GenerationAdapter(Protocol):
    @property
    def provider_name(self) -> str:
        ...

    @property
    def model_name(self) -> str:
        ...

    @property
    def revision(self) -> str:
        ...

    def generate_answer(
        self,
        query: str,
        context: ContextPackage,
        task: str = "generate",
    ) -> tuple[StructuredAnswer, int, int]:
        """Generate structured answer returning (answer, input_tokens, output_tokens)."""
        ...
