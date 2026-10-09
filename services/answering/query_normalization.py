"""Safe query expansions for well-defined official-authority acronyms."""

import re


_ATO = re.compile(r"\bATO\b", re.IGNORECASE)
_ATO_EXPANSION = "Australian Taxation Office (ATO)"


def expand_official_acronyms(query: str) -> str:
    """Add the canonical ATO name so hybrid retrieval can find its official pages."""
    return _ATO.sub(_ATO_EXPANSION, query)
