"""Hash-bound professional-review and project-owner waiver checks."""

from datetime import datetime
import json
from pathlib import Path

from .gold import gold_sha256


SUPPORTED_SCHEMA_VERSION = "fintax-domain-review-governance-1.0"


def load_review_record(path: Path) -> dict:
    return json.loads(path.read_text()) if path.is_file() else {}


def _base_failures(gold_path: Path, record: dict) -> list[str]:
    failures = []
    if not record:
        return ["domain-review governance record is missing"]
    if record.get("schema_version") != SUPPORTED_SCHEMA_VERSION:
        failures.append(f"review schema_version must be {SUPPORTED_SCHEMA_VERSION}")
    if record.get("gold_sha256") != gold_sha256(gold_path):
        failures.append("review governance is not bound to the current gold set")
    return failures


def _timestamp_failure(record: dict, key: str) -> str | None:
    value = str(record.get(key) or "").strip()
    if not value:
        return f"review governance is missing {key}"
    try:
        datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return f"{key} is not ISO-8601"
    return None


def governance_failures(gold_path: Path, record_path: Path) -> list[str]:
    record = load_review_record(record_path)
    failures = _base_failures(gold_path, record)
    if not record:
        return failures
    status = record.get("status")
    if status == "approved":
        for key in ("reviewer_name", "reviewer_qualification"):
            if not str(record.get(key) or "").strip():
                failures.append(f"professional approval is missing {key}")
        if failure := _timestamp_failure(record, "approved_at"):
            failures.append(failure)
    elif status == "waived":
        if record.get("waiver_authority") != "project_owner":
            failures.append("waiver_authority must be project_owner")
        for key in ("waiver_reason", "architecture_revision"):
            if not str(record.get(key) or "").strip():
                failures.append(f"review waiver is missing {key}")
        if failure := _timestamp_failure(record, "waived_at"):
            failures.append(failure)
    else:
        failures.append("domain review status must be approved or waived")
    return failures


def approval_failures(gold_path: Path, record_path: Path) -> list[str]:
    record = load_review_record(record_path)
    failures = _base_failures(gold_path, record)
    if not record:
        return failures
    if record.get("status") != "approved":
        failures.append("qualified professional review was not performed")
        return failures
    for key in ("reviewer_name", "reviewer_qualification"):
        if not str(record.get(key) or "").strip():
            failures.append(f"professional approval is missing {key}")
    if failure := _timestamp_failure(record, "approved_at"):
        failures.append(failure)
    return failures
