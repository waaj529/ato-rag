"""Structure-aware chunking service."""

from .core import ChunkerConfig, catalog_record, chunk_document
from .records import sizing_units

__all__ = ["ChunkerConfig", "catalog_record", "chunk_document", "sizing_units"]
