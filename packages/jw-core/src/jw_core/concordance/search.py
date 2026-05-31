"""Search API over the FTS5 concordance index.

Supports the native FTS5 query grammar: phrase ("..."), AND/OR/NOT,
prefix (foo*), and NEAR/N proximity. Regex is **not** supported — the
goal is deterministic literal/lexical matching, not pattern expansion.

The snippet renderer marks the matched span with the Unicode delimiters
`SNIPPET_START` (`‹`) and `SNIPPET_END` (`›`) so the output is Markdown
and HTML safe by default.
"""

from __future__ import annotations

import re
from pathlib import Path

from jw_core.concordance.models import ConcordanceHit
from jw_core.concordance.store import ConcordanceStore

SNIPPET_START = "‹"
SNIPPET_END = "›"
_REGEX_RED_FLAGS = re.compile(r"\\b|\\d|\\s|\\w|\[|\]|\{|\}|\+\B|\^|\$")
# Match `›<whitespace>‹` so we can collapse adjacent matched tokens into a
# single highlighted span: `‹brown› ‹fox›` → `‹brown fox›`. Improves
# readability and makes substring assertions like `"brown fox"` work.
_ADJACENT_SPANS_RE = re.compile(re.escape(SNIPPET_END) + r"(\s+)" + re.escape(SNIPPET_START))


# ── Query helpers ──────────────────────────────────────────────────────


def escape_fts_phrase(text: str) -> str:
    """Quote `text` for use as an FTS5 phrase ("..."), doubling inner quotes."""

    return '"' + text.replace('"', '""') + '"'


def is_safe_query(query: str) -> bool:
    """Reject queries that look like regex (we're not a regex engine)."""

    return _REGEX_RED_FLAGS.search(query) is None


# ── Search ─────────────────────────────────────────────────────────────


def concordance_search(
    query: str,
    *,
    language: str | None = None,
    source_kind: str | None = None,
    max_results: int = 100,
    db_path: Path | None = None,
) -> list[ConcordanceHit]:
    """Run a literal FTS5 search and return hits sorted by FTS rank."""

    if not query.strip():
        return []
    if not is_safe_query(query):
        raise ValueError(
            "concordance_search does not support regex metacharacters. "
            "Use phrases (\"...\") and AND/OR/NEAR instead."
        )

    sql = [
        "SELECT e.entry_id, e.source_kind, e.source_id, e.ref, e.language, e.url, "
        "snippet(concordance_fts, 0, ?, ?, '…', 8) AS snip "
        "FROM concordance_fts f JOIN concordance_entries e ON e.entry_id = f.rowid "
        "WHERE concordance_fts MATCH ?",
    ]
    params: list[object] = [SNIPPET_START, SNIPPET_END, query]
    if language:
        sql.append("AND e.language = ?")
        params.append(language)
    if source_kind:
        sql.append("AND e.source_kind = ?")
        params.append(source_kind)
    sql.append("ORDER BY rank LIMIT ?")
    params.append(int(max_results))

    store = ConcordanceStore(db_path=db_path)
    try:
        rows = store._conn.execute(" ".join(sql), params).fetchall()
    finally:
        store.close()

    return [
        ConcordanceHit(
            entry_id=row["entry_id"],
            source_kind=row["source_kind"],
            source_id=row["source_id"],
            ref=row["ref"],
            snippet=_ADJACENT_SPANS_RE.sub(r"\1", row["snip"]),
            language=row["language"],
            url=row["url"],
        )
        for row in rows
    ]
