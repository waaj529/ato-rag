"""Exact character-span chunk splitting with structural boundaries."""

from dataclasses import dataclass
import re

from .text import TOKEN_RE


@dataclass(frozen=True)
class TextSpan:
    text: str
    char_start: int
    char_end: int
    token_count: int


def _is_boundary(text: str, left_end: int, right_start: int, left_token: str) -> bool:
    gap = text[left_end:right_start]
    return bool(re.search(r"\n\s*\n", gap)) or left_token in {".", "!", "?", ";"}


def _choose_end(text: str, matches: list, start: int, target: int, hard_max: int) -> int:
    remaining = len(matches) - start
    if remaining <= hard_max:
        return len(matches)
    lower = min(start + max(1, target // 2), len(matches))
    upper = min(start + hard_max, len(matches))
    ideal = min(start + target, upper)
    candidates = []
    for index in range(lower, upper + 1):
        if index == len(matches):
            candidates.append(index)
            continue
        previous = matches[index - 1]
        current = matches[index]
        if _is_boundary(text, previous.end(), current.start(), previous.group()):
            candidates.append(index)
    return min(candidates, key=lambda value: abs(value - ideal)) if candidates else ideal


def split_spans(text: str, *, target: int, hard_max: int, overlap: int = 0) -> list[TextSpan]:
    matches = list(TOKEN_RE.finditer(text))
    if not matches:
        return []
    result = []
    start = 0
    while start < len(matches):
        end = _choose_end(text, matches, start, target, hard_max)
        char_start = matches[start].start()
        char_end = matches[end - 1].end()
        result.append(TextSpan(text[char_start:char_end], char_start, char_end, end - start))
        if end == len(matches):
            break
        start = max(start + 1, end - overlap) if overlap else end
    return result

