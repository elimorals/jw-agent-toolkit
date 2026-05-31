"""convention_discovery — detect convention years + videos from JW Broadcasting.

VISION.md Module 6 / Gap 8: "Asambleas regionales/circuito: detección
automática de fechas + materiales relacionados".

JW doesn't expose regional convention DATES via a public API (those are
distributed by branch offices). What jw.org DOES expose is the year-
indexed convention category (`{YYYY}Convention`) on the mediator API
once the program is published.

Strategy:

  1. Walk `VODProgramsEvents` subcategories and pick out `\\d{4}Convention`.
  2. For each year, fetch the videos and emit a generic `Event` with
     `start_iso` = mid-year (June 1) as a placeholder when the user
     hasn't recorded a precise date locally.
  3. Honor any explicit overrides the user has in their `EventStore`.

This gives users a starting point — "Convention 2026 material is
available, last published video on YYYY-MM-DD" — and lets them refine
the actual local dates manually.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from datetime import date

from jw_core.calendar.events import Event, EventStore
from jw_core.clients.jw_broadcasting import JWBroadcastingClient

from jw_agents.base import AgentResult, Citation, Finding

logger = logging.getLogger(__name__)

_CONV_KEY_RE = re.compile(r"(\d{4})Convention$")
_ROOT_CATEGORY = "VODProgramsEvents"


@dataclass
class ConventionListing:
    year: int
    category_key: str
    video_count: int
    sample_titles: list[str]


async def convention_discovery(
    *,
    language: str = "en",
    client: JWBroadcastingClient | None = None,
    insert_into_event_store: bool = True,
    event_store: EventStore | None = None,
    start_month: int = 6,  # placeholder month for the synthetic event
) -> AgentResult:
    """Detect available convention years and surface them as findings."""
    result = AgentResult(query=_ROOT_CATEGORY, agent_name="convention_discovery")
    result.metadata["language"] = language

    owned = client is None
    client = client or JWBroadcastingClient()
    try:
        top = await client.get_category(_ROOT_CATEGORY, language=language)
    except Exception as e:
        result.warnings.append(f"Walk failed: {e}")
        return result
    listings: list[ConventionListing] = []
    for key in top.subcategories:
        match = _CONV_KEY_RE.match(key)
        if not match:
            continue
        year = int(match.group(1))
        try:
            cat = await client.get_category(key, language=language)
        except Exception as e:
            result.warnings.append(f"convention {year} fetch failed: {e}")
            continue
        sample_titles = [v.title for v in cat.videos[:3] if v.title]
        listings.append(
            ConventionListing(
                year=year,
                category_key=key,
                video_count=len(cat.videos),
                sample_titles=sample_titles,
            )
        )
    if owned:
        await client.aclose()

    result.metadata["years"] = [l.year for l in listings]

    owned_store = event_store is None and insert_into_event_store
    store: EventStore | None = (
        event_store if event_store is not None else (EventStore() if insert_into_event_store else None)
    )
    try:
        for listing in listings:
            placeholder_start = date(listing.year, start_month, 1).isoformat()
            placeholder_end = date(listing.year, start_month, 3).isoformat()
            existing = None
            if store is not None:
                existing = next(
                    (e for e in store.list_all(kind="convention") if e.start_iso.startswith(str(listing.year))),
                    None,
                )
                if existing is None:
                    event = Event(
                        kind="convention",
                        title=f"Regional Convention {listing.year}",
                        start_iso=placeholder_start,
                        end_iso=placeholder_end,
                        language=language,
                        notes=(
                            f"Auto-detected from JW Broadcasting "
                            f"({listing.video_count} videos under {listing.category_key}). "
                            "Update dates with your local schedule."
                        ),
                        tags=["auto_detected", "convention"],
                    )
                    store.upsert(event)
                    event_iso = placeholder_start
                else:
                    event_iso = existing.start_iso
            else:
                event_iso = placeholder_start
            result.findings.append(
                Finding(
                    summary=f"Convention {listing.year} — {listing.video_count} videos available",
                    excerpt="; ".join(listing.sample_titles)[:300],
                    citation=Citation(
                        url=f"https://www.jw.org/{language}/library/videos/#{listing.category_key}",
                        title=f"{listing.year} Convention",
                        kind="convention",
                        metadata={
                            "year": listing.year,
                            "category_key": listing.category_key,
                            "event_start_iso": event_iso,
                        },
                    ),
                    metadata={"source": "convention_discovery", "year": listing.year},
                )
            )
    finally:
        if owned_store and store is not None:
            store.close()
    return result
