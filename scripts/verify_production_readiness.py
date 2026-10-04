#!/usr/bin/env python3
"""Record current verification evidence and external blockers without reusing old phase scores."""

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import sys
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

GROUPS = {
    "generation": ("FINTAX_LLM_ENDPOINT", "FINTAX_LLM_API_KEY", "FINTAX_LLM_PROVIDER", "FINTAX_LLM_MODEL", "FINTAX_LLM_REVISION"),
    "langfuse": ("LANGFUSE_HOST", "LANGFUSE_PUBLIC_KEY", "LANGFUSE_SECRET_KEY"),
    "authentication": ("FINTAX_OIDC_ISSUER", "FINTAX_OIDC_AUDIENCE", "FINTAX_OIDC_JWKS_URL"),
    "database": ("FINTAX_DATABASE_URL",),
}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--test-report", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    suites = ET.parse(args.test_report).getroot().findall("testsuite")
    counts = {key: sum(int(s.get(key, "0")) for s in suites) for key in ("tests", "failures", "errors", "skipped")}
    source_digest = hashlib.sha256()
    violations = []
    for folder in ("apps", "packages", "services", "scripts", "tests"):
        for path in sorted((ROOT / folder).rglob("*.py")):
            data = path.read_bytes()
            source_digest.update(str(path.relative_to(ROOT)).encode() + b"\0" + data)
            if len(data.splitlines()) > 150:
                violations.append(str(path.relative_to(ROOT)))
    missing = {group: [name for name in names if not os.environ.get(name)] for group, names in GROUPS.items()}
    report = {
        "schema_version": "fintax-readiness-2", "created_at": datetime.now(timezone.utc).isoformat(),
        "status": "blocked", "broad_production_authorized": False,
        "source_tree_sha256": source_digest.hexdigest(), "source_line_limit_violations": violations,
        "test_report_sha256": hashlib.sha256(args.test_report.read_bytes()).hexdigest(),
        "test_results": counts, "test_report": str(args.test_report),
        "configuration_missing": missing,
        "phase5": {"status": "blocked", "live_generation_evaluated": False,
                   "independent_factual_accuracy": None, "jev_integration": "not_configured"},
        "phase6": {"status": "blocked", "deployed_oidc_verified": False,
                   "remote_langfuse_verified": False, "remote_retention_verified": False,
                   "deployed_least_privilege_verified": False, "object_versioning_verified": False,
                   "pitr_verified": False, "full_corpus_restore_verified": False},
        "phase7": {"status": "blocked", "organic_trial_for_changed_code": "not_run"},
        "historical_phase5_phase7_metrics_reused": False,
        "notes": ["Test report is local engineering evidence, not deployed product accuracy.",
                  "Live configuration and independent reviewer records are still required.",
                  "In-process rate limiting is not a distributed deployment quota."],
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("x") as handle:
        json.dump(report, handle, indent=2)
    print(json.dumps(report, indent=2))
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
