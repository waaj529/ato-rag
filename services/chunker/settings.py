"""Chunker constants and validated sizing configuration."""

from dataclasses import dataclass


CHUNKER_VERSION = "legal-structure-v2"
TOKENIZER_VERSION = "unicode-lexical-v1"


@dataclass(frozen=True)
class ChunkerConfig:
    child_target_tokens: int = 600
    child_hard_max_tokens: int = 900
    overlap_tokens: int = 60
    parent_target_tokens: int = 2000
    parent_hard_max_tokens: int = 2500

    def validate(self) -> None:
        if not 0 <= self.overlap_tokens < self.child_target_tokens:
            raise ValueError("overlap_tokens must be smaller than child_target_tokens")
        if self.child_target_tokens > self.child_hard_max_tokens:
            raise ValueError("child target cannot exceed child hard maximum")
        if self.parent_target_tokens > self.parent_hard_max_tokens:
            raise ValueError("parent target cannot exceed parent hard maximum")
