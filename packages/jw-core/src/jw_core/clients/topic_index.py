"""Client for the Watch Tower Publications Index (topic / subject pages).

Two operations:

  1. `search_subjects(query)` — find candidate subject pages by running a
     CDN search with `filter='indexes'` and extracting their WOL URLs +
     docids.
  2. `get_subject_page(docid_or_url)` — fetch and parse a subject page.

The subject pages live at `wol.jw.org/{lang}/wol/d/{resource}/{lp_tag}/{docid}`.
We accept either a bare docid (with optional language) or a full URL.
"""

from __future__ import annotations

import logging
import re
from typing import Any

import httpx

from jw_core.cache import DiskCache
from jw_core.clients.cdn import CDNClient
from jw_core.clients.wol import WOLClient
from jw_core.languages import get_language
from jw_core.models import TopicSubject
from jw_core.parsers.topic_index import parse_subject_page
from jw_core.telemetry import Telemetry
from jw_core.throttle import Throttler

logger = logging.getLogger(__name__)

# Search results return URLs in two flavors:
#   path style:  /en/wol/d/r1/lp-e/1200275936
#   query style: /wol/finder?wtlocale=E&docid=1200273853&p=doc&srcid=
_DOCID_RE = re.compile(r"/d/[^/]+/[^/]+/(\d+)|[?&]docid=(\d+)")


class TopicIndexError(RuntimeError):
    pass


class TopicIndexClient:
    """High-level client over CDN search + WOL for the Publications Index."""

    def __init__(
        self,
        cdn: CDNClient | None = None,
        wol: WOLClient | None = None,
        http: httpx.AsyncClient | None = None,
        *,
        throttler: Throttler | None = None,
        cache: DiskCache | None = None,
        telemetry: Telemetry | None = None,
    ) -> None:
        # CDN and WOL inherit Phase 9 deps if not pre-wired.
        self._cdn = cdn or CDNClient(
            http=http, throttler=throttler, cache=cache, telemetry=telemetry,
        )
        self._wol = wol or WOLClient(
            http=http, throttler=throttler, cache=cache, telemetry=telemetry,
        )
        self._owns_cdn = cdn is None
        self._owns_wol = wol is None

    async def search_subjects(
        self,
        query: str,
        *,
        language: str = "E",
        limit: int = 10,
        rerank_by_title_match: bool = True,
    ) -> list[dict[str, Any]]:
        """Find topic-index entries matching `query`.

        Uses the CDN search with `filter='indexes'`. Returns a list of
        candidate subjects with `title`, `snippet`, `wol_url`, `docid`,
        and a `score` indicating ranking confidence.

        Phase 4.7 reranking: when `rerank_by_title_match=True`, subjects
        whose title closely matches the query (case-insensitive exact or
        substring match) are boosted to the top. This fixes the case where
        a query like 'Trinity' would otherwise return tangentially-related
        subjects (e.g. 'Hermas') ahead of the actual 'TRINITY' subject.
        """
        try:
            data = await self._cdn.search(
                query, filter_type="indexes", language=language, limit=limit
            )
        except Exception as e:
            raise TopicIndexError(f"Subject search failed: {e}") from e

        out: list[dict[str, Any]] = []
        for original_rank, entry in enumerate(_flatten_search_results(data)):
            links = entry.get("links", {}) or {}
            url = links.get("wol") or links.get("jw.org") or ""
            docid = ""
            if url:
                m = _DOCID_RE.search(url)
                if m:
                    docid = m.group(1) or m.group(2) or ""
            out.append({
                "title": entry.get("title", ""),
                "snippet": entry.get("snippet", ""),
                "wol_url": url,
                "docid": docid,
                "subtype": entry.get("subtype", ""),
                "original_rank": original_rank,
                "score": 0.0,  # filled in below
            })

        if rerank_by_title_match:
            out = _rerank_by_title_match(out, query)
        return out

    async def get_subject_page(
        self,
        docid_or_url: str,
        *,
        language: str = "en",
    ) -> TopicSubject:
        """Fetch and parse a subject page by docid or full URL."""
        if not docid_or_url:
            raise TopicIndexError("Empty docid_or_url — nothing to fetch.")
        url = self._resolve_url(docid_or_url, language)
        html = await self._wol.fetch(url)
        parsed = parse_subject_page(html, source_url=url, language=language)
        if parsed is None:
            raise TopicIndexError(f"Could not parse subject page at {url}")
        return parsed

    @staticmethod
    def _resolve_url(docid_or_url: str, language: str) -> str:
        if docid_or_url.startswith("http"):
            return docid_or_url
        if "/" in docid_or_url:
            return f"https://wol.jw.org{docid_or_url if docid_or_url.startswith('/') else '/' + docid_or_url}"
        # Plain docid → build URL using the language's resource version.
        lang = get_language(language)
        return (
            f"https://wol.jw.org/{lang.iso}/wol/d/{lang.wol_resource}/"
            f"{lang.lp_tag}/{docid_or_url}"
        )

    async def aclose(self) -> None:
        if self._owns_cdn:
            await self._cdn.aclose()
        if self._owns_wol:
            await self._wol.aclose()


def _flatten_search_results(data: dict[str, Any]) -> list[dict[str, Any]]:
    """Pull every dict-typed result entry out of the (sometimes grouped) shape."""
    out: list[dict[str, Any]] = []
    for r in data.get("results", []):
        if not isinstance(r, dict):
            continue
        if r.get("type") == "group":
            out.extend(x for x in r.get("results", []) if isinstance(x, dict))
        else:
            out.append(r)
    return out


def _rerank_by_title_match(
    results: list[dict[str, Any]], query: str
) -> list[dict[str, Any]]:
    """Score results by title proximity to the query and resort.

    Score is a float in [0, 100]:
      100: title exactly equals query (case-insensitive)
       80: title starts with query
       60: query is a whole word in title
       40: title contains query as substring
       20: any query token appears in title
        0: no match

    On ties, the original CDN rank breaks them (so the underlying engine's
    judgement is preserved when our heuristic gives no signal).
    """
    q_lower = query.lower().strip()
    q_tokens = {t for t in re.split(r"\W+", q_lower) if len(t) > 1}
    word_re = re.compile(rf"\b{re.escape(q_lower)}\b") if q_lower else None
    # "startswith as a word": query at position 0 AND followed by a
    # non-word char (or end). Prevents "God" from matching "Goddess".
    startswith_word_re = (
        re.compile(rf"^{re.escape(q_lower)}(?:\b|\W|$)") if q_lower else None
    )

    for r in results:
        title = r.get("title", "").lower()
        score = 0.0
        if title and q_lower:
            if title == q_lower:
                score = 100.0
            elif startswith_word_re and startswith_word_re.search(title):
                score = 80.0
            elif word_re and word_re.search(title):
                score = 60.0
            elif q_lower in title:
                score = 40.0
            elif q_tokens and any(t in title for t in q_tokens):
                score = 20.0
        r["score"] = score

    # Sort: higher score first, then original rank ascending.
    return sorted(
        results,
        key=lambda r: (-r["score"], r["original_rank"]),
    )
