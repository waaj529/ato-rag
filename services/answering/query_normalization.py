"""Safe query expansions for well-defined official-authority acronyms."""

import re


_ATO = re.compile(r"\bATO\b", re.IGNORECASE)
_ATO_EXPANSION = "Australian Taxation Office (ATO)"
_CANONICAL_ATO_PREFIX = "australian taxation office ("


def expand_official_acronyms(query: str) -> str:
    """Add the canonical ATO name so hybrid retrieval can find its official pages."""
    def expand(match: re.Match[str]) -> str:
        prefix = query[:match.start()].casefold()
        return match.group(0) if prefix.endswith(_CANONICAL_ATO_PREFIX) else _ATO_EXPANSION

    return _ATO.sub(expand, query)
