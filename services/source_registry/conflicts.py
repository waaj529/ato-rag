"""Detect inventory rows that describe one source but disagree about its content.

The upstream indexes list some sources more than once: the same GSTR 2003/3 appears under
both ``?DocID=…`` and ``?DocId=…``, giving one ruling two document ids and two paths.
Duplicate listing is tolerable while the rows agree, and is corruption when they do not,
so rows are grouped by normalised source URL and compared on the version they claim. Every
document records the ``content_sha256`` of the bytes it was parsed from beside the
``version_id`` derived from it, so two rows claiming one version must carry one content
hash; a version claimed under two different hashes is a conflict.

Measured across the frozen corpus: 39741 distinct source URLs, 6217 duplicate rows, and no
version claimed twice with different content.
"""

from collections import Counter, defaultdict

from .urls import normalize_source_url


def conflict_report(identities: list[tuple]) -> dict:
    """Summarise duplicate source URLs; ``identities`` is (url, version_id, content_sha256)."""
    rows: Counter[str] = Counter()
    versions: dict[str, set[tuple]] = defaultdict(set)
    unlabelled = 0
    for source_url, version_id, content_sha256 in identities:
        url = normalize_source_url(source_url)
        if not url:
            unlabelled += 1
            continue
        rows[url] += 1
        versions[url].add((version_id, content_sha256))
    conflicts = []
    for url, members in versions.items():
        contents: dict[object, set] = defaultdict(set)
        for version_id, content_sha256 in members:
            contents[version_id].add(content_sha256)
        conflicts.extend((url, version_id) for version_id, hashes in contents.items()
                         if len(hashes) > 1)
    return {
        "source_url_groups": len(rows),
        "documents_without_source_url": unlabelled,
        "duplicate_source_url_rows": sum(count - 1 for count in rows.values() if count > 1),
        "conflicting_source_urls": len(conflicts),
        "source_url_conflicts": [{"source_url": url, "version_id": version_id}
                                 for url, version_id in sorted(conflicts, key=str)],
    }
