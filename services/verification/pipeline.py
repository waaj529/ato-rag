"""Fail-closed grounded answer generation, validation and repair pipeline."""

from collections.abc import Callable
from dataclasses import dataclass
from typing import Sequence

from packages.security import PermissionScope, ScopeSafetyPolicyGate, resolve_and_enforce_scope
from packages.telemetry import span
from services.context_builder import ContextPackage
from services.generation import ModelRouter, StructuredAnswer
from services.source_registry import CorpusScopeGate, ScopeStatus
from .adequacy import AdequacyStatus, EvidenceAdequacyController
from .judge import HeuristicEvidenceJudge
from .models import EvidenceState, JudgeDecision, ValidationResult
from .validators import DeterministicValidator


@dataclass(frozen=True)
class PipelineResponse:
    query: str
    answer: StructuredAnswer
    validation: ValidationResult
    judge: JudgeDecision
    repaired: bool
    abstained: bool
    decision_reason: str = "ADEQUATE_ANSWERED"


class GroundedAnswerPipeline:
    def __init__(
        self,
        router: ModelRouter | None = None,
        validator: DeterministicValidator | None = None,
        judge: HeuristicEvidenceJudge | None = None,
        adequacy_controller: EvidenceAdequacyController | None = None,
        policy_gate: ScopeSafetyPolicyGate | None = None,
        scope_gate: CorpusScopeGate | None = None,
    ) -> None:
        self.router = router or ModelRouter()
        self.validator = validator or DeterministicValidator()
        self.judge = judge or HeuristicEvidenceJudge()
        self.adequacy = adequacy_controller or EvidenceAdequacyController()
        self.policy = policy_gate or ScopeSafetyPolicyGate()
        self.scope_gate = scope_gate or CorpusScopeGate()

    def run(
        self,
        query: str,
        context: ContextPackage,
        permission_scope: PermissionScope | None = None,
        retry_hook: Callable[[str], ContextPackage] | None = None,
    ) -> PipelineResponse:
        resolve_and_enforce_scope(permission_scope)

        policy_dec = self.policy.evaluate(query)
        if not policy_dec.passed:
            return self.policy_refusal(query, policy_dec.code, policy_dec.reason)

        scope_dec = self.scope_gate.evaluate(query)
        if scope_dec.status == ScopeStatus.OUT_OF_CORPUS:
            return self.scope_refusal(query, scope_dec.code, scope_dec.reason)

        with span("evidence_adequacy_evaluation"):
            status, reasons = self.adequacy.evaluate(query, context)

        if status == AdequacyStatus.WEAK and retry_hook is not None:
            rewritten = self.adequacy.rewrite_query(query)
            context = retry_hook(rewritten)
            with span("evidence_adequacy_retry"):
                status, reasons = self.adequacy.evaluate(rewritten, context)

        if status != AdequacyStatus.ADEQUATE:
            abstention = StructuredAnswer(
                answer_markdown="FinTaxGPT cannot confirm this response against the authoritative corpus without ambiguity.",
                claims=(),
                limitations=tuple(reasons) + ("Abstained due to insufficient authoritative evidence.",),
                needs_human_review=True,
            )
            return PipelineResponse(
                query=query, answer=abstention,
                validation=ValidationResult(passed=True, errors=(), evidence_state=EvidenceState.INSUFFICIENT_EVIDENCE, resolved_citations=()),
                judge=JudgeDecision(evidence_support=1.0, answer_completeness=1.0, relevance=1.0, unsupported_claim_risk=0.0, evaluation_kind="not_evaluated"),
                repaired=False, abstained=True,
                decision_reason=reasons[0] if reasons else "EVIDENCE_INADEQUATE",
            )

        draft = self.router.generate(query, context)
        with span("deterministic_validation"):
            val_res = self.validator.validate(draft, context)
        judge_res = self.judge.judge(query, draft, context)

        if val_res.passed:
            return PipelineResponse(
                query=query, answer=draft, validation=val_res,
                judge=judge_res, repaired=False, abstained=False,
                decision_reason="ADEQUATE_ANSWERED",
            )

        # Single bounded repair pass
        repaired_draft = self.router.repair(draft, val_res.errors, context)
        with span("final_validation"):
            final_val = self.validator.validate(repaired_draft, context)
        final_judge = self.judge.judge(query, repaired_draft, context)

        if final_val.passed:
            return PipelineResponse(
                query=query, answer=repaired_draft, validation=final_val,
                judge=final_judge, repaired=True, abstained=False,
                decision_reason="REPAIRED_ANSWERED",
            )

        # Fail-closed informative abstention
        abstention = StructuredAnswer(
            answer_markdown="FinTaxGPT cannot confirm this response against the authoritative corpus without ambiguity.",
            claims=(),
            limitations=tuple(final_val.errors) + ("Abstained following failed deterministic validation.",),
            needs_human_review=True,
        )
        return PipelineResponse(
            query=query, answer=abstention, validation=final_val,
            judge=final_judge, repaired=True, abstained=True,
            decision_reason="VALIDATION_FAILED",
        )

    @classmethod
    def _refusal(cls, query: str, prefix: str, code: str, reason: str, msg: str) -> PipelineResponse:
        abstention = StructuredAnswer(
            answer_markdown=msg, claims=(),
            limitations=(f"{prefix}: {code} - {reason}",), needs_human_review=False,
        )
        return PipelineResponse(
            query=query, answer=abstention,
            validation=ValidationResult(passed=True, errors=(), evidence_state=EvidenceState.INSUFFICIENT_EVIDENCE, resolved_citations=()),
            judge=JudgeDecision(evidence_support=1.0, answer_completeness=1.0, relevance=1.0, unsupported_claim_risk=0.0, evaluation_kind="not_evaluated"),
            repaired=False, abstained=True, decision_reason=f"{prefix}:{code}",
        )

    @classmethod
    def policy_refusal(cls, query: str, code: str, reason: str) -> PipelineResponse:
        return cls._refusal(query, "POLICY_REJECTED", code, reason, "FinTaxGPT cannot process this request under product safety boundaries.")

    @classmethod
    def scope_refusal(cls, query: str, code: str, reason: str) -> PipelineResponse:
        return cls._refusal(query, "OUT_OF_CORPUS", code, reason, "FinTaxGPT cannot answer this question because the subject matter is outside the published Australian taxation and revenue law corpus.")
