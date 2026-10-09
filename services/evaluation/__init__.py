"""Evaluation contracts for phase gates and retrieval benchmarks."""

from .independent import evidence_hash, evaluate_review
from .review_models import ReviewedCase, AnswerReview
from .acceptance import FALSE_ABSTENTION_TARGET, classify_acceptance
from .gold import GoldValidation, validate_gold_set
from .pilot import PilotFeedback, compute_pilot_metrics, simulate_pilot_feedback
from .optional_deepeval import deepeval_is_missing
try:
    from .deepeval_adapter import create_llm_test_case, pipeline_response_to_test_case
    from .deepeval_metrics import (
        build_answer_relevancy_metric,
        build_contextual_precision_metric,
        build_contextual_recall_metric,
        build_contextual_relevancy_metric,
        build_faithfulness_metric,
        build_rag_metric_suite,
        build_statutory_compliance_metric,
    )
    from .deepeval_runner import evaluate_test_case, run_deepeval_suite
except ModuleNotFoundError as error:
    if not deepeval_is_missing(error):
        raise
    create_llm_test_case = None
    pipeline_response_to_test_case = None
    build_answer_relevancy_metric = None
    build_contextual_precision_metric = None
    build_contextual_recall_metric = None
    build_contextual_relevancy_metric = None
    build_faithfulness_metric = None
    build_rag_metric_suite = None
    build_statutory_compliance_metric = None
    evaluate_test_case = None
    run_deepeval_suite = None
from .staging import (
    StagingQueryRecord,
    StagingUserFeedback,
    load_staging_records,
    log_staging_record,
    summarize_staging_trial,
)

__all__ = [
    "ReviewedCase",
    "AnswerReview",
    "evidence_hash",
    "evaluate_review",
    "GoldValidation",
    "FALSE_ABSTENTION_TARGET",
    "PilotFeedback",
    "RetrievalBenchmark",
    "StagingQueryRecord",
    "StagingUserFeedback",
    "build_answer_relevancy_metric",
    "build_contextual_precision_metric",
    "build_contextual_recall_metric",
    "build_contextual_relevancy_metric",
    "build_faithfulness_metric",
    "build_rag_metric_suite",
    "build_statutory_compliance_metric",
    "classify_acceptance",
    "create_llm_test_case",
    "evaluate_test_case",
    "load_staging_records",
    "log_staging_record",
    "relevant_rank",
    "run_deepeval_suite",
    "simulate_pilot_feedback",
    "summarize_staging_trial",
    "pipeline_response_to_test_case",
    "validate_gold_set",
]
