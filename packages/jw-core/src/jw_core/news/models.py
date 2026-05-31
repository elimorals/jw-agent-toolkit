"""Pydantic models for the news monitor.

NewsItem — one piece of upstream content (a magazine, a video, a workbook).
SeenRecord — what's already in the local store.
DigestReport — what the CLI / MCP tool returns; serializable.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

Channel = Literal["publications", "broadcasting", "programs"]


class NewsItem(BaseModel):
    """One upstream item observed in a source's current response."""

    channel: Channel
    item_id: str
    title: str
    language: str
    url: str
    description: str = ""
    first_published: datetime | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class SeenRecord(BaseModel):
    """A row from the local seen-store."""

    channel: str
    item_id: str
    first_seen_at: datetime
    last_seen_at: datetime
    metadata: dict[str, Any] = Field(default_factory=dict)


class DigestReport(BaseModel):
    """Aggregate result of one digest run."""

    generated_at: datetime
    since: datetime | None
    languages: list[str]
    channels: list[str]
    new_items: list[NewsItem]
    retired_items: list[SeenRecord]
    markdown: str
    warnings: list[str] = Field(default_factory=list)

    def stats(self) -> dict[str, int]:
        base = {
            "new": len(self.new_items),
            "retired": len(self.retired_items),
            "by_channel:publications": 0,
            "by_channel:broadcasting": 0,
            "by_channel:programs": 0,
        }
        for item in self.new_items:
            key = f"by_channel:{item.channel}"
            base[key] = base.get(key, 0) + 1
        return base
