"""Independent reviewed propositions, source validity and answer-bound claim labels."""

from datetime import date
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class ReviewModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ExpectedSource(ReviewModel):
    document_id: str = Field(min_length=1)
    version_id: str = Field(min_length=1)
    official_url: str = Field(min_length=1)
    locator: dict = Field(min_length=1)
    valid_from: date
    valid_to: date | None = None

    @model_validator(mode="after")
    def valid_interval(self):
        if self.valid_to and self.valid_to < self.valid_from:
            raise ValueError("Invalid source validity interval")
        return self


class ExpectedProposition(ReviewModel):
    proposition_id: str = Field(min_length=1)
    text: str = Field(min_length=1)
    sources: list[ExpectedSource] = Field(min_length=1)


class ReviewedCase(ReviewModel):
    case_id: str = Field(min_length=1)
    question: str = Field(min_length=1)
    as_of: date
    must_abstain: bool
    reviewer_id: str = Field(min_length=1)
    propositions: list[ExpectedProposition]

    @model_validator(mode="after")
    def propositions_required(self):
        ids = [p.proposition_id for p in self.propositions]
        if len(ids) != len(set(ids)) or (not self.must_abstain and not ids):
            raise ValueError("Answerable gold needs unique independently reviewed propositions")
        return self


class ClaimReview(ReviewModel):
    claim_id: str = Field(min_length=1)
    proposition_id: str | None
    entailed_by_cited_evidence: bool = Field(strict=True)


class AnswerReview(ReviewModel):
    case_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    response_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    reviewer_id: str = Field(min_length=1)
    method: Literal["independent_human_review"]
    all_material_claims_enumerated: bool = Field(strict=True)
    claims: list[ClaimReview]
