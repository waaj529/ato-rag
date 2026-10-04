"""Canonical identity for an official source URL.

Two inventory rows describe one document only when their URLs identify the same source,
but the upstream export varies query-parameter *case* for identical URLs: the same
GSTR 2003/3 is indexed as both ``?DocID=…`` and ``?DocId=…``, producing two document ids
and two paths for one ruling. Measured across the frozen corpus, parameter-name casing is
the only variation that actually occurs (``docid`` 1394, ``DocId`` 438, ``DocID`` 324 rows)
and no tracking parameters are present, so the key case-folds parameter names,
canonicalises percent-encoding and sorts parameters, and leaves paths, values and
fragments untouched.
"""

from urllib.parse import parse_qsl, unquote, urlencode, urlsplit, urlunsplit


def normalize_source_url(source_url: object) -> str:
    """Return a stable identity key for an official source URL."""
    parts = urlsplit(str(source_url or "").strip())
    parameters = sorted(
        (unquote(name).casefold(), unquote(value))
        for name, value in parse_qsl(parts.query, keep_blank_values=True)
    )
    return urlunsplit((
        parts.scheme.casefold(), parts.netloc.casefold(),
        unquote(parts.path), urlencode(parameters), parts.fragment,
    ))
