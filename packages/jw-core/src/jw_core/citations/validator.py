"""Citation integrity validator.

This file is built up incrementally across Fase 23 tasks. In this slice we
ship only the URL parser and the agent-output extractor — the validator
class itself arrives in Task 4.
"""

from __future__ import annotations

import re
from typing import Any


_WOL_DOC_RE = re.compile(
    r"^https?://wol\.jw\.org/(?P<iso>[a-z]{2,3})/wol/d/[^/]+/[^/]+/(?P<doc_id>\d+)/?$"
)
_WOL_BIBLE_RE = re.compile(
    r"^https?://wol\.jw\.org/(?P<iso>[a-z]{2,3})/wol/b/[^/]+/[^/]+/(?P<pub>[^/]+)(?:/[^/]+)+/?$"
)


def _parse_wol_url(url: str) -> dict[str, Any] | None:
    """Parse a wol.jw.org URL into its structural pieces.

    Recognized patterns (from `docs/ARCHITECTURE.md`):
      /{iso}/wol/d/{r}/{lp_tag}/{docId}
      /{iso}/wol/b/{r}/{lp_tag}/{pub}/{book_num}/{chapter}

    Returns None for any URL we don't recognize (b.jw-cdn.org, external, ...).
    """

    m = _WOL_DOC_RE.match(url)
    if m:
        return {"doc_id": int(m.group("doc_id")), "pub_code": None, "iso": m.group("iso")}
    m = _WOL_BIBLE_RE.match(url)
    if m:
        return {"doc_id": None, "pub_code": m.group("pub"), "iso": m.group("iso")}
    return None


def _extract_urls(agent_output: Any) -> list[str]:
    """Pull deduplicated, order-preserved URLs out of an AgentResult-like.

    Accepts a dict (already-serialized) OR any object exposing `.findings`
    where each finding has metadata.citation_url or finding.citation.url.
    """

    seen: set[str] = set()
    urls: list[str] = []

    if isinstance(agent_output, dict):
        findings = agent_output.get("findings", []) or []
        candidates = []
        for f in findings:
            if not isinstance(f, dict):
                continue
            url = (f.get("metadata") or {}).get("citation_url")
            if not url:
                citation = f.get("citation") or {}
                url = citation.get("url") if isinstance(citation, dict) else None
            candidates.append(url)
    else:
        findings = getattr(agent_output, "findings", []) or []
        candidates = []
        for f in findings:
            meta = getattr(f, "metadata", None) or {}
            url = meta.get("citation_url") if isinstance(meta, dict) else None
            if not url:
                citation = getattr(f, "citation", None)
                url = getattr(citation, "url", None) if citation else None
            candidates.append(url)

    for url in candidates:
        if not url or url in seen:
            continue
        seen.add(url)
        urls.append(url)
    return urls
