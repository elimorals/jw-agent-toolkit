"""News monitor — detect new jw.org publications, broadcasting videos, and
monthly meeting program drops.

Public API:
    from jw_core.news import (
        NewsItem, SeenRecord, DigestReport,
        SeenStore,
        PublicationsSource, BroadcastingSource, ProgramsSource, NewsSource,
        build_digest, collect_items, diff_against_store, render_markdown,
    )
"""

from jw_core.news.digest import (
    build_digest,
    collect_items,
    diff_against_store,
    render_markdown,
)
from jw_core.news.models import DigestReport, NewsItem, SeenRecord
from jw_core.news.sources import (
    BroadcastingSource,
    NewsSource,
    ProgramsSource,
    PublicationsSource,
)
from jw_core.news.store import SeenStore

__all__ = [
    "BroadcastingSource",
    "DigestReport",
    "NewsItem",
    "NewsSource",
    "ProgramsSource",
    "PublicationsSource",
    "SeenRecord",
    "SeenStore",
    "build_digest",
    "collect_items",
    "diff_against_store",
    "render_markdown",
]
