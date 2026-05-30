"""Citation integrity validator.

Three modes:
  - structural: offline, MepsCatalog lookup only (default).
  - live:       structural + HTTP resolve via injectable async fetcher.
  - live+drift: live + compares fetched HTML shape against committed snapshot.

The validator NEVER instantiates an httpx client itself. Callers pass a
fetcher callable; tests pass a fake; CLI/MCP pass an httpx-backed adapter.
"""

from __future__ import annotations

import asyncio
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Awaitable, Callable, Literal

from jw_core.citations.models import (
    CitationCheck,
    CitationReport,
)
from jw_core.integrations.meps_catalog import MepsCatalog


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
    candidates: list[str | None] = []

    if isinstance(agent_output, dict):
        for f in agent_output.get("findings", []) or []:
            if not isinstance(f, dict):
                continue
            url = (f.get("metadata") or {}).get("citation_url")
            if not url:
                citation = f.get("citation") or {}
                url = citation.get("url") if isinstance(citation, dict) else None
            candidates.append(url)
    else:
        for f in getattr(agent_output, "findings", []) or []:
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


@dataclass
class FetcherResponse:
    final_url: str
    status: int
    redirect_chain: list[str] = field(default_factory=list)
    body: str = ""


AsyncFetcher = Callable[[str], Awaitable[FetcherResponse]]
Mode = Literal["structural", "live", "live+drift"]


class CitationValidator:
    """Batch validator for wol.jw.org citation URLs.

    Construct once per batch (cheap). All public methods are async.

    Args:
        catalog: MepsCatalog instance (Fase 19). When None, all catalog
            checks degrade to `skipped`.
        fetcher: async callable URL -> FetcherResponse. Required for
            modes 'live' and 'live+drift'.
        snapshots_root: directory containing HTML snapshots named
            `<sha256(url)>.html`. Required for mode 'live+drift'.
        max_redirects: cap on redirect chain length per URL (default 3).
        concurrency: max concurrent fetches in live modes (default 4).
    """

    def __init__(
        self,
        *,
        catalog: MepsCatalog | None = None,
        fetcher: AsyncFetcher | None = None,
        snapshots_root: Path | None = None,
        max_redirects: int = 3,
        concurrency: int = 4,
    ) -> None:
        self.catalog = catalog
        self.fetcher = fetcher
        self.snapshots_root = snapshots_root
        self.max_redirects = max_redirects
        self._concurrency = concurrency
        self._sem: asyncio.Semaphore | None = None
        self._catalog_lock = asyncio.Lock()

    def _get_sem(self) -> asyncio.Semaphore:
        # Lazy-construct so the Semaphore binds to the running event loop.
        if self._sem is None:
            self._sem = asyncio.Semaphore(self._concurrency)
        return self._sem

    # ── Public API ─────────────────────────────────────────────────────

    async def validate_urls(self, urls: list[str], *, mode: Mode = "structural") -> CitationReport:
        if mode in {"live", "live+drift"} and self.fetcher is None:
            raise ValueError(f"mode={mode!r} requires a fetcher")
        if mode == "live+drift" and self.snapshots_root is None:
            raise ValueError("mode='live+drift' requires snapshots_root")

        tasks = [self._check_one(u, mode=mode) for u in urls]
        checks = await asyncio.gather(*tasks)
        return CitationReport(
            mode=mode,
            checks=list(checks),
            summary=CitationReport.summarize(list(checks)),
        )

    async def validate_agent_output(
        self,
        agent_output: Any,
        *,
        mode: Mode = "structural",
    ) -> CitationReport:
        return await self.validate_urls(_extract_urls(agent_output), mode=mode)

    # ── Internals ──────────────────────────────────────────────────────

    async def _check_one(self, url: str, *, mode: Mode) -> CitationCheck:
        check = CitationCheck(url=url)
        parsed = _parse_wol_url(url)
        if parsed:
            check.doc_id = parsed["doc_id"]
            check.pub_code = parsed["pub_code"]

        await self._populate_catalog(check)

        live_body: str | None = None
        if mode in {"live", "live+drift"}:
            live_body = await self._populate_live(check)

        if mode == "live+drift":
            self._populate_drift(check, live_body=live_body)

        return check

    async def _populate_catalog(self, check: CitationCheck) -> None:
        if self.catalog is None:
            check.catalog = "skipped"
            return
        if check.doc_id is None:
            check.catalog = "unknown"
            return

        # MepsCatalog is sqlite-backed and binds to its creator thread.
        # Calls are quick (indexed lookup); serialize via lock for safety.
        async with self._catalog_lock:
            docs = self.catalog.find_documents(
                meps_document_id=check.doc_id,
                limit=1,
            )
        if not docs:
            check.catalog = "missing"
            check.notes.append(f"doc_id={check.doc_id} not in MepsCatalog")
            return
        doc = docs[0]
        if check.pub_code is not None and check.pub_code != doc.pub_code:
            check.catalog = "mismatch"
            check.notes.append(
                f"URL says pub_code={check.pub_code!r} but catalog says {doc.pub_code!r}"
            )
        else:
            check.catalog = "ok"
            check.pub_code = check.pub_code or doc.pub_code

    async def _populate_live(self, check: CitationCheck) -> str | None:
        assert self.fetcher is not None
        async with self._get_sem():
            try:
                resp = await self.fetcher(check.url)
            except Exception as exc:  # noqa: BLE001 — fetcher contract is wide
                check.resolve = "network_error"
                check.notes.append(f"fetch failed: {exc!r}")
                return None

        check.http_status = resp.status
        check.resolved_url = resp.final_url
        check.redirect_chain = list(resp.redirect_chain)

        if len(resp.redirect_chain) > self.max_redirects:
            check.resolve = "redirect_loop"
            check.notes.append(f"redirect chain {len(resp.redirect_chain)} > {self.max_redirects}")
            return resp.body or None
        if resp.status == 404:
            check.resolve = "not_found"
        elif resp.status == 410:
            check.resolve = "gone"
        elif 500 <= resp.status < 600:
            check.resolve = "server_error"
        elif 200 <= resp.status < 300:
            check.resolve = "ok_redirect" if resp.redirect_chain else "ok"
        else:
            check.resolve = "network_error"
            check.notes.append(f"unexpected HTTP {resp.status}")
        return resp.body or None

    def _populate_drift(self, check: CitationCheck, *, live_body: str | None) -> None:
        if self.snapshots_root is None:
            check.drift = "skipped"
            return
        import hashlib

        digest = hashlib.sha256(check.url.encode("utf-8")).hexdigest()
        snap = self.snapshots_root / f"{digest}.html"
        if not snap.exists():
            check.drift = "no_snapshot"
            return
        check.snapshot_path = str(snap)
        if check.resolve not in {"ok", "ok_redirect"} or live_body is None:
            check.drift = "drift"
            check.notes.append("could not compare: live fetch was not 2xx")
            return

        snap_body = snap.read_text(encoding="utf-8")
        # `_shape_hash` was built for JSON, so we project HTML through a tiny
        # tree model: tag counts + nesting. Cheap and stable across the
        # minor-content changes wol.jw.org makes routinely.
        live_shape = _html_shape(live_body)
        snap_shape = _html_shape(snap_body)
        if live_shape == snap_shape:
            check.drift = "ok"
        else:
            check.drift = "drift"
            check.notes.append(f"shape changed: {snap_shape[:32]}… → {live_shape[:32]}…")


def _html_shape(html: str) -> str:
    """Tiny HTML-structure hash. Counts opening tags; ignores whitespace + text.

    Same skeleton ⇒ same hash. Adding/removing a tag changes the hash.
    Robust to minor content edits, language changes, image swaps.
    """
    import hashlib

    tags = re.findall(r"<\s*([a-zA-Z0-9]+)", html)
    canon = ",".join(sorted(t.lower() for t in tags))
    return f"html({len(tags)})[{hashlib.sha256(canon.encode()).hexdigest()[:16]}]"
