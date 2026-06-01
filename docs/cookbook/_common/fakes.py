"""Fakes shared across cookbook recipes. No network."""

from __future__ import annotations

from typing import Any


class FakeCDNClient:
    """Async stub of jw_core.clients.cdn.CDNClient with canned search results."""

    def __init__(self, canned: list[dict[str, Any]] | None = None) -> None:
        self.canned = canned or [
            {
                "title": "What Does the Bible Really Teach About God?",
                "url": "https://wol.jw.org/en/wol/d/r1/lp-e/1102002129",
                "snippet": "The Bible answers fundamental questions about God's nature...",
            },
        ]
        self.calls: list[tuple[str, dict[str, Any]]] = []

    async def search(self, query: str, *, limit: int = 5, **kwargs: Any) -> dict[str, Any]:
        self.calls.append((query, kwargs))
        return {"results": self.canned[:limit], "query": query}


class FakeWOLClient:
    """Async stub of jw_core.clients.wol.WOLClient. Returns canned HTML."""

    def __init__(self, html: str = "<html><body>Stub WOL body</body></html>") -> None:
        self.html = html
        self.calls: list[str] = []

    async def fetch(self, url: str) -> str:
        self.calls.append(url)
        return self.html


class FakeEmbedder:
    """Deterministic zero-vector embedder mirroring the Fase 41 Protocol."""

    name = "fake-cookbook"
    target = "cpu"
    dim = 4

    def is_available(self) -> bool:
        return True

    def embed(self, texts: list[str]):
        import numpy as np

        return np.zeros((len(texts), self.dim), dtype=np.float32)
