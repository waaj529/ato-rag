#!/usr/bin/env python3
"""Export the frozen 300 benchmark cases to reviewer-friendly CSV and HTML formats."""

import csv
import html
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from services.chunker.validation import SourceResolver
from services.source_registry import normalize_document

GOLD_PATH = ROOT / "evals/australia_tax_legal_gold.jsonl"
IMPORT_PATHS = (ROOT / "data/imports/ato_ready.json", ROOT / "data/imports/court_ready.json")
CSV_PATH = ROOT / "evals/domain_review_sheet.csv"
HTML_PATH = ROOT / "evals/domain_review_sheet.html"


def _build_rows(cases: list[dict], resolver: SourceResolver) -> list[dict]:
    rows = []
    for case in cases:
        passage = next(iter(case["expected_passages"]), None)
        if passage is None:
            rows.append({
                "case_id": case["id"], "question": case["question"],
                "document_title": "No expected authority", "source_class": "N/A",
                "binding_authority": "N/A", "applicable_period": "N/A",
                "expected_passage": "Must abstain", "source_url": "",
                "must_abstain": "YES", "acceptable_alternatives": "None",
                "reviewer_decision": "", "reviewer_notes": "",
            })
            continue
        doc = normalize_document(resolver.document(passage["document_id"]))
        cls = doc.get("classification") or {}
        periods = ", ".join(cls.get("applicable_periods", [])) or (case.get("as_of_date") or "N/A")
        rows.append({
            "case_id": case["id"],
            "question": case["question"],
            "document_title": doc.get("title", ""),
            "source_class": cls.get("source_class", ""),
            "binding_authority": f"{cls.get('binding_effect', 'none')} (rank {cls.get('authority_rank', 100)})",
            "applicable_period": periods,
            "expected_passage": passage.get("text", ""),
            "source_url": doc.get("source_url", ""),
            "must_abstain": "YES" if case.get("must_abstain") else "NO",
            "acceptable_alternatives": "; ".join(case.get("acceptable_alternatives", [])) or "None",
            "reviewer_decision": "",
            "reviewer_notes": "",
        })
    return rows


def _write_csv(rows: list[dict], path: Path) -> None:
    fieldnames = list(rows[0].keys())
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def _write_html(rows: list[dict], path: Path) -> None:
    head = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8"><title>FinTaxGPT Phase 0 Domain Review Sheet</title>
<style>
body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; margin: 20px; background: #f8fafc; color: #0f172a; }
h1 { margin-bottom: 4px; }
p.meta { color: #64748b; font-size: 14px; margin-top: 0; }
table { width: 100%; border-collapse: collapse; background: #fff; box-shadow: 0 1px 3px rgba(0,0,0,0.1); font-size: 13px; }
th, td { padding: 10px 12px; border: 1px solid #e2e8f0; text-align: left; vertical-align: top; }
th { background: #0f172a; color: #fff; position: sticky; top: 0; }
tr:nth-child(even) { background: #f1f5f9; }
.passage { font-family: ui-monospace, SFMono-Regular, monospace; background: #f8fafc; padding: 6px; border-radius: 4px; border: 1px solid #cbd5e1; max-width: 320px; word-break: break-word; }
.tag { display: inline-block; padding: 2px 6px; border-radius: 4px; font-size: 11px; font-weight: 600; background: #e2e8f0; }
</style>
</head>
<body>
<h1>FinTaxGPT Phase 0 Domain Review Sheet (300 Benchmark Cases)</h1>
<p class="meta">Frozen benchmark: <code>evals/australia_tax_legal_gold.jsonl</code> | Target: Australian Tax & Legal Domain Review</p>
<table>
<thead><tr>
<th>ID</th><th>Question</th><th>Document / Source</th><th>Authority & Timing</th><th>Expected Answer Passage</th><th>URL</th><th>Decision</th><th>Notes</th>
</tr></thead><tbody>"""
    lines = [head]
    for r in rows:
        url = html.escape(r["source_url"])
        source_link = (f'<a href="{url}" target="_blank" rel="noopener">Source</a>'
                       if url else "N/A")
        lines.append(f"""<tr>
<td><b>{html.escape(r['case_id'])}</b></td>
<td>{html.escape(r['question'])}</td>
<td><b>{html.escape(r['document_title'])}</b><br><span class="tag">{html.escape(r['source_class'])}</span></td>
<td>{html.escape(r['binding_authority'])}<br><small>Period: {html.escape(r['applicable_period'])}</small></td>
<td><div class="passage">{html.escape(r['expected_passage'])}</div></td>
<td>{source_link}</td>
<td>[ &nbsp; ] PASS<br>[ &nbsp; ] FAIL<br>[ &nbsp; ] CHANGE</td>
<td></td>
</tr>""")
    lines.append("</tbody></table></body></html>")
    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    resolver = SourceResolver(IMPORT_PATHS)
    with GOLD_PATH.open(encoding="utf-8") as handle:
        cases = [json.loads(line) for line in handle if line.strip()]
    rows = _build_rows(cases, resolver)
    _write_csv(rows, CSV_PATH)
    _write_html(rows, HTML_PATH)
    print(f"Exported {len(rows)} cases to:\n - {CSV_PATH}\n - {HTML_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
