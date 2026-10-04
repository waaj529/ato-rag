"""Deterministic exact and near-duplicate candidate removal."""

import re

from .models import HydratedCandidate


WORD = re.compile(r"[a-z0-9]{2,}")


def _terms(value: str) -> frozenset[str]:
    return frozenset(WORD.findall(value.casefold()))


def _similar(left: frozenset[str], right: frozenset[str], threshold: float) -> bool:
    if left == right:
        return True
    union = left | right
    return bool(union) and len(left & right) / len(union) >= threshold


def dedupe_candidates(values: tuple[HydratedCandidate, ...],
                      threshold: float) -> tuple[HydratedCandidate, ...]:
    kept: list[HydratedCandidate] = []
    fingerprints: list[frozenset[str]] = []
    for value in values:
        fingerprint = _terms(value.content)
        if any(_similar(fingerprint, prior, threshold) for prior in fingerprints):
            continue
        kept.append(value)
        fingerprints.append(fingerprint)
    return tuple(kept)
