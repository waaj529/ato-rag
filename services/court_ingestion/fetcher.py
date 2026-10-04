"""Restricted fetcher for explicitly listed official Australian court sources."""

from dataclasses import dataclass
import hashlib
from pathlib import Path
from urllib.parse import urlparse
from urllib.request import Request, urlopen


OFFICIAL_HOSTS = frozenset({
    "www.judgments.fedcourt.gov.au",
    "judgments.fedcourt.gov.au",
    "www.hcourt.gov.au",
    "eresources.hcourt.gov.au",
    "dls.hcourt.gov.au",
})
USER_AGENT = "FinTaxGPT/0.1 official-court-ingestion"
MAX_BYTES = 20 * 1024 * 1024


@dataclass(frozen=True)
class CourtSource:
    source_url: str
    court: str
    neutral_citation: str


@dataclass(frozen=True)
class FetchedSource:
    source: CourtSource
    body: bytes
    content_type: str
    raw_sha256: str


def validate_source(source: CourtSource) -> None:
    parsed = urlparse(source.source_url)
    if parsed.scheme != "https" or parsed.hostname not in OFFICIAL_HOSTS:
        raise ValueError(f"source is not an allowlisted official court URL: {source.source_url}")
    if not source.neutral_citation.startswith("["):
        raise ValueError("neutral_citation must be explicit in the seed manifest")


def fetch_source(source: CourtSource, timeout: int = 30) -> FetchedSource:
    validate_source(source)
    accepted = "text/html,application/xhtml+xml,application/pdf,application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    request = Request(source.source_url, headers={"User-Agent": USER_AGENT, "Accept": accepted})
    with urlopen(request, timeout=timeout) as response:
        final_host = urlparse(response.geturl()).hostname
        if final_host not in OFFICIAL_HOSTS:
            raise ValueError(f"official source redirected to a non-allowlisted host: {final_host}")
        content_type = response.headers.get_content_type()
        if content_type not in {"text/html", "application/xhtml+xml", "application/pdf",
                                "application/vnd.openxmlformats-officedocument.wordprocessingml.document"}:
            raise ValueError(f"unsupported court response type: {content_type}")
        body = response.read(MAX_BYTES + 1)
    if len(body) > MAX_BYTES:
        raise ValueError("court response exceeds the 20 MiB safety limit")
    return FetchedSource(source, body, content_type, hashlib.sha256(body).hexdigest())


def load_local_source(source: CourtSource, path: Path, expected_sha256: str) -> FetchedSource:
    """Load a manually downloaded official judgment and verify its pinned digest."""
    validate_source(source)
    if len(expected_sha256) != 64 or any(value not in "0123456789abcdef" for value in expected_sha256):
        raise ValueError("expected_sha256 must be a lowercase SHA-256 digest")
    if not path.is_file():
        raise ValueError(f"manual court file is missing: {path}")
    body = path.read_bytes()
    if len(body) > MAX_BYTES:
        raise ValueError("manual court file exceeds the 20 MiB safety limit")
    actual = hashlib.sha256(body).hexdigest()
    if actual != expected_sha256:
        raise ValueError(f"manual court file SHA-256 mismatch: expected {expected_sha256}, got {actual}")
    suffix = path.suffix.casefold()
    content_type = {
        ".pdf": "application/pdf",
        ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    }.get(suffix)
    if content_type is None:
        raise ValueError("manual court file must be PDF or DOCX")
    if suffix == ".pdf" and not body.startswith(b"%PDF-"):
        raise ValueError("manual PDF does not have a PDF signature")
    if suffix == ".docx" and not body.startswith(b"PK"):
        raise ValueError("manual DOCX does not have a ZIP signature")
    return FetchedSource(source, body, content_type, actual)
