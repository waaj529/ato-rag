"""Adapter converting FinTaxGPT artifacts into DeepEval LLMTestCases."""

from typing import Sequence

from deepeval.test_case import LLMTestCase
from services.context_builder import ContextPackage
from services.verification import PipelineResponse


def create_llm_test_case(
    query: str,
    actual_output: str,
    retrieval_context: Sequence[str],
    expected_output: str | None = None,
    context: Sequence[str] | None = None,
) -> LLMTestCase:
    """Create a validated DeepEval LLMTestCase for RAG evaluation."""
    if not query.strip():
        raise ValueError("Query cannot be empty for LLMTestCase")
    if not actual_output.strip():
        raise ValueError("Actual output cannot be empty for LLMTestCase")

    return LLMTestCase(
        input=query,
        actual_output=actual_output,
        retrieval_context=list(retrieval_context) if retrieval_context else [],
        expected_output=expected_output,
        context=list(context) if context else None,
    )


def pipeline_response_to_test_case(
    response: PipelineResponse,
    context: ContextPackage,
    expected_output: str | None = None,
) -> LLMTestCase:
    """Construct an LLMTestCase directly from pipeline response and evidence package."""
    retrieval_context = [unit.text for unit in context.evidence if unit.text]
    output_text = response.answer.answer_markdown
    if not output_text and response.abstained:
        output_text = "I cannot answer this question based on the verified evidence."

    return create_llm_test_case(
        query=response.query,
        actual_output=output_text,
        retrieval_context=retrieval_context,
        expected_output=expected_output,
    )
