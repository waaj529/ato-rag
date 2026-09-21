"""Deterministic text tokenization and identity normalization."""

import re


TOKEN_RE = re.compile(r"\w+(?:['’\-]\w+)*|[^\w\s]", re.UNICODE)
TABLE_LINE_RE = re.compile(r"(?m)^\s*\|.*\|\s*$")


def tokens(text: str) -> list[str]:
    return TOKEN_RE.findall(text or "")


def token_count(text: str) -> int:
    return len(tokens(text))


def normalize_identity_text(text: str) -> str:
    return re.sub(r"\s+", " ", text or "").strip()


def strip_markdown_tables(text: str) -> str:
    cleaned = TABLE_LINE_RE.sub("", text or "")
    return re.sub(r"\n{3,}", "\n\n", cleaned).strip()

