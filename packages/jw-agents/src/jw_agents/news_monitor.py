"""news_monitor agent — thin async wrapper that wires sources to the digest
builder and returns an `AgentResult` with one `Finding` per new item.

Default behaviour wires real clients via `jw_core.clients.factory.build_clients`,
but tests/eval can inject stub sources + a stub store for full isolation.

Returns an AgentResult so MCP/CLI surfaces see the same envelope as every
other agent.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from jw_core.clients.factory import build_clients
from jw_core.clients.jw_broadcasting import JWBroadcastingClient
from jw_core.news.digest import build_digest
from jw_core.news.models import DigestReport
from jw_core.news.sources import (
    BroadcastingSource,
    NewsSource,
    ProgramsSource,
    PublicationsSource,
)
from jw_core.news.store import SeenStore

from jw_agents.base import AgentResult, Citation, Finding

logger = logging.getLogger(__name__)

DEFAULT_LANGUAGES = ["en", "es", "pt"]
DEFAULT_CHANNELS = ["publications", "broadcasting", "programs"]


def _resolve_since(since: str | None, store: SeenStore) -> datetime | None:
    if since is None or since == "last_run":
        return store.last_run_at()
    if since == "epoch":
        return None
    try:
        dt = datetime.fromisoformat(since)
    except ValueError as exc:
        raise ValueError(
            f"--since must be 'last_run', 'epoch' or ISO-8601 date, got {since!r}"
        ) from exc
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def _default_sources() -> list[NewsSource]:
    clients = build_clients()
    bcst = JWBroadcastingClient(
        throttler=clients.throttler,
        cache=clients.cache,
        telemetry=clients.telemetry,
    )
    return [
        PublicationsSource(client=clients.pub_media),
        BroadcastingSource(client=bcst),
        ProgramsSource(client=clients.pub_media),
    ]


async def news_monitor(
    *,
    since: str | None = "last_run",
    languages: list[str] | None = None,
    channels: list[str] | None = None,
    sources: list[NewsSource] | None = None,
    store: SeenStore | None = None,
    update: bool = True,
    now: datetime | None = None,
) -> AgentResult:
    """Run the news monitor and return an AgentResult.

    Args:
        since: "last_run" (default), "epoch", or an ISO date string.
        languages: ISO codes (en/es/pt/...). Default ["en","es","pt"].
        channels: subset of {"publications","broadcasting","programs"}.
        sources: inject stubs for testing; default wires real clients.
        store: inject for tests; default SeenStore() uses ~/.jw-agent-toolkit/.
        update: when True, mark seen items and advance last_run.
        now: clock injection for determinism in tests.
    """

    languages = languages or DEFAULT_LANGUAGES
    channels = channels or DEFAULT_CHANNELS
    owned_store = store is None
    store = store or SeenStore()
    owned_sources = sources is None
    sources = sources if sources is not None else _default_sources()

    try:
        since_dt = _resolve_since(since, store)
        report: DigestReport = await build_digest(
            sources=sources,
            store=store,
            languages=languages,
            channels=channels,
            since=since_dt,
            update=update,
            now=now,
        )
    finally:
        if owned_store:
            store.close()
        if owned_sources:
            # Real clients own httpx; close them so we don't leak.
            for s in sources:
                client = getattr(s, "_client", None)
                aclose = getattr(client, "aclose", None)
                if aclose:
                    try:
                        await aclose()
                    except Exception as exc:  # noqa: BLE001
                        logger.debug("source close failed: %s", exc)

    result = AgentResult(query=f"news_digest since={since}", agent_name="news_monitor")
    result.metadata.update(
        {
            "since": since,
            "since_resolved": since_dt.isoformat() if since_dt else "epoch",
            "languages": languages,
            "channels": channels,
            "stats": report.stats(),
            "markdown": report.markdown,
            "warnings": report.warnings,
            "retired": [r.model_dump(mode="json") for r in report.retired_items],
        }
    )
    for item in report.new_items:
        result.findings.append(
            Finding(
                summary=f"[{item.channel}/{item.language}] {item.title}",
                citation=Citation(
                    url=item.url,
                    title=item.title,
                    kind=item.channel,
                    metadata=item.metadata,
                ),
                excerpt=item.description,
                metadata={
                    "source": "news_monitor",
                    "channel": item.channel,
                    "item_id": item.item_id,
                    "language": item.language,
                },
            )
        )
    for w in report.warnings:
        result.warnings.append(w)
    return result
