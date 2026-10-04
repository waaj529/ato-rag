import os
from typing import Any

os.environ.setdefault("DEEPEVAL_TELEMETRY_OPT_OUT", "YES")

from deepeval.metrics import (
    AnswerRelevancyMetric,
    ContextualPrecisionMetric,
    ContextualRecallMetric,
    ContextualRelevancyMetric,
    FaithfulnessMetric,
    GEval,
)
try:
    from deepeval.test_case import SingleTurnParams as TestCaseParams
except ImportError:  # pragma: no cover
    from deepeval.test_case import LLMTestCaseParams as TestCaseParams


def build_faithfulness_metric(threshold: float = 0.7, model: Any = None) -> FaithfulnessMetric:
    return FaithfulnessMetric(threshold=threshold, model=model, async_mode=False)


def build_answer_relevancy_metric(threshold: float = 0.7, model: Any = None) -> AnswerRelevancyMetric:
    return AnswerRelevancyMetric(threshold=threshold, model=model, async_mode=False)


def build_contextual_precision_metric(threshold: float = 0.7, model: Any = None) -> ContextualPrecisionMetric:
    return ContextualPrecisionMetric(threshold=threshold, model=model, async_mode=False)


def build_contextual_recall_metric(threshold: float = 0.7, model: Any = None) -> ContextualRecallMetric:
    return ContextualRecallMetric(threshold=threshold, model=model, async_mode=False)


def build_contextual_relevancy_metric(threshold: float = 0.7, model: Any = None) -> ContextualRelevancyMetric:
    return ContextualRelevancyMetric(threshold=threshold, model=model, async_mode=False)


def build_statutory_compliance_metric(threshold: float = 0.7, model: Any = None) -> GEval:
    criteria = (
        "Assess whether the actual output correctly adheres to Australian taxation "
        "and legal authority. The response must not hallucinate repealed statutory sections, "
        "must cite provisions accurately (e.g. s 6-5 ITAA97, s 8-1 ITAA97), and must only "
        "assert legal propositions that are strictly grounded in the retrieved legal context."
    )
    return GEval(
        name="Australian Statutory Compliance",
        criteria=criteria,
        evaluation_params=[
            TestCaseParams.INPUT,
            TestCaseParams.ACTUAL_OUTPUT,
            TestCaseParams.RETRIEVAL_CONTEXT,
        ],
        threshold=threshold,
        model=model,
        async_mode=False,
    )


def build_rag_metric_suite(
    threshold: float = 0.7,
    model: Any = None,
    include_custom: bool = True,
) -> list[Any]:
    suite = [
        build_faithfulness_metric(threshold, model),
        build_answer_relevancy_metric(threshold, model),
        build_contextual_precision_metric(threshold, model),
        build_contextual_recall_metric(threshold, model),
        build_contextual_relevancy_metric(threshold, model),
    ]
    if include_custom:
        suite.append(build_statutory_compliance_metric(threshold, model))
    return suite
