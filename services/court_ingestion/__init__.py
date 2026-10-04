"""Official-court adapter producing verified ``ready-document-1.0`` records."""

from .fetcher import CourtSource, fetch_source, load_local_source
from .parser import parse_judgment
from .records import ready_document

__all__ = ["CourtSource", "fetch_source", "load_local_source", "parse_judgment", "ready_document"]
