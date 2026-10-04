"""Map a parsed official judgment into the canonical ready-document contract."""

from datetime import datetime
import hashlib
import json
import uuid

from .fetcher import FetchedSource
from .parser import ParsedJudgment


NAMESPACE = uuid.UUID("0dd69ff1-f847-4f49-9180-f65b143d44dc")


def _iso_date(value: str | None) -> str | None:
    if not value:
        return None
    try:
        return datetime.strptime(value, "%d %B %Y").date().isoformat()
    except ValueError:
        return None


def ready_document(fetched: FetchedSource, parsed: ParsedJudgment) -> dict:
    source = fetched.source
    document_id = str(uuid.uuid5(NAMESPACE, source.source_url))
    sections = [{
        "section_id": f"para_{number}",
        "heading": f"Paragraph {number}",
        "heading_path": [parsed.title, f"Paragraph {number}"],
        "level": 2,
        "text": text,
        "source_locator": {"paragraph_start": number, "paragraph_end": number},
    } for number, text in parsed.paragraphs]
    content = "\n\n".join(section["text"] for section in sections)
    content_sha256 = hashlib.sha256(content.encode()).hexdigest()
    suffix = {"application/pdf": "pdf",
              "application/vnd.openxmlformats-officedocument.wordprocessingml.document": "docx"}.get(
                  fetched.content_type, "html")
    record = {
        "schema_version": "ready-document-1.0", "document_id": document_id,
        "title": parsed.title, "publisher": source.court, "source_url": source.source_url,
        "canonical_reference_id": source.neutral_citation,
        "classification": {"corpus": "court_judgments", "document_type": "Judgment",
            "source_class": "court_decision", "topics": ["Taxation"],
            "applicable_periods": [], "page_status": "current",
            "binding_effect": "judicial_precedent", "authority_rank": 15},
        "dates": {"decision_date": _iso_date(parsed.decision_date)},
        "case_metadata": {"court": source.court, "neutral_citation": source.neutral_citation,
            "case_name": parsed.title, "judges": list(parsed.judges)},
        "provenance": {"raw_object_key": f"raw/{fetched.raw_sha256}.{suffix}",
            "raw_sha256": fetched.raw_sha256},
        "version": {"version_id": f"v1_{fetched.raw_sha256[:16]}",
            "raw_sha256": fetched.raw_sha256, "content_sha256": content_sha256},
        "sections": sections, "tables": [], "references": [],
    }
    json.dumps(record, ensure_ascii=False)
    return record
