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

# Temporary minimal __init__.py — restored to full surface in Task 6.
from jw_core.news.models import DigestReport, NewsItem, SeenRecord

__all__ = ["DigestReport", "NewsItem", "SeenRecord"]
