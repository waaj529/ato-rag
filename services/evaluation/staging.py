"""Staging trial tracking and practitioner feedback recording (Phase 7)."""

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Literal

from packages.telemetry import get_current_span

DEFAULT_STAGING_LOG = Path("data/evaluations/staging_trial_records.jsonl")
TRIAL_LABEL = "staging / not formal professional validation"

FinalDecision = Literal[
    "answered",
    "safety-refused",
    "out-of-corpus",
    "inadequate-evidence",
]
AbstentionAssessment = Literal["correct", "unnecessarily-conservative", "not-applicable"]


@dataclass(frozen=True)
class StagingUserFeedback:
    user_id: str
    user_role: str
    useful: bool
    abstention_assessment: AbstentionAssessment
    user_correction: str | None = None
    abstention_root_cause: str | None = None


@dataclass(frozen=True)
class StagingQueryRecord:
    query_id: str
    query: str
    timestamp: str
    final_decision: FinalDecision
    corpus_scope_reason: str | None
    evidence_adequacy_reason: str | None
    retrieved_authorities: tuple[str, ...]
    reranker_scores: tuple[float, ...]
    generation_model: str
    judge_decision: dict
    latency_ms: float
    cost_usd: float | None
    trace_id: str
    user_feedback: StagingUserFeedback | None = None

    def to_dict(self) -> dict:
        return asdict(self)

    def trace_attributes(self) -> dict[str, object]:
        feedback = self.user_feedback
        return {
            "trial.label": TRIAL_LABEL,
            "trial.query_id": self.query_id,
            "decision.final": self.final_decision,
            "decision.corpus_scope_reason": self.corpus_scope_reason or "not-applicable",
            "decision.evidence_adequacy_reason": self.evidence_adequacy_reason or "not-applicable",
            "retrieval.authorities": list(self.retrieved_authorities),
            "reranker.scores": list(self.reranker_scores),
            "generation.model": self.generation_model,
            "jev.decision": self.judge_decision,
            "query.latency_ms": self.latency_ms,
            "query.cost_usd": self.cost_usd,
            "feedback.useful": feedback.useful if feedback else "pending",
            "feedback.abstention_assessment": feedback.abstention_assessment if feedback else "pending",
            "feedback.correction": feedback.user_correction if feedback else "pending",
        }


def log_staging_record(record: StagingQueryRecord, log_path: Path = DEFAULT_STAGING_LOG) -> None:
    active_span = get_current_span()
    if active_span is not None:
        active_span.attributes.update(record.trace_attributes())
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with open(log_path, "a", encoding="utf-8") as f:
        f.write(json.dumps(record.to_dict(), ensure_ascii=False) + "\n")


def load_staging_records(log_path: Path = DEFAULT_STAGING_LOG) -> list[dict]:
    if not log_path.exists():
        return []
    records = []
    with open(log_path, "r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                records.append(json.loads(line))
    return records


def summarize_staging_trial(records: list[dict]) -> dict:
    total = len(records)
    if total == 0:
        return {"trial_label": TRIAL_LABEL, "total_queries": 0}

    decisions: dict[str, int] = {}
    abstentions_conservative = 0
    abstentions_correct = 0
    useful_count = 0
    feedback_count = 0
    root_causes: dict[str, int] = {}

    for r in records:
        dec = r.get("final_decision", "unknown")
        decisions[dec] = decisions.get(dec, 0) + 1
        fb = r.get("user_feedback")
        if fb:
            feedback_count += 1
            if fb.get("useful"):
                useful_count += 1
            assessment = fb.get("abstention_assessment")
            if assessment == "unnecessarily-conservative":
                abstentions_conservative += 1
                cause = fb.get("abstention_root_cause") or "unclassified"
                root_causes[cause] = root_causes.get(cause, 0) + 1
            elif assessment == "correct":
                abstentions_correct += 1

    return {
        "trial_label": TRIAL_LABEL,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "total_queries_logged": total,
        "feedback_received_count": feedback_count,
        "decisions_breakdown": decisions,
        "user_satisfaction_rate": round(useful_count / feedback_count, 4) if feedback_count else None,
        "conservative_abstentions_count": abstentions_conservative,
        "correct_abstentions_count": abstentions_correct,
        "abstention_root_causes": root_causes,
    }
