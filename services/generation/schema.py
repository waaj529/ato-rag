"""Strict wire schema and deterministic rendering of every generated material claim."""

from pydantic import BaseModel, ConfigDict, Field

from .models import Claim, StructuredAnswer


class WireClaim(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    claim_id: str = Field(min_length=1)
    text: str = Field(min_length=1)
    evidence_ids: list[str]


class WireAnswer(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    claims: list[WireClaim]
    limitations: list[str]
    needs_human_review: bool

    def to_answer(self) -> StructuredAnswer:
        claims = tuple(Claim(c.claim_id, c.text, tuple(c.evidence_ids)) for c in self.claims)
        # Free-form prose cannot bypass the material-claim validator.
        markdown = "\n\n".join(f"{c.text} [{', '.join(c.evidence_ids)}]" for c in claims)
        return StructuredAnswer(markdown or "Insufficient evidence to answer.", claims,
                                tuple(self.limitations), self.needs_human_review)
