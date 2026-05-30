"""Locate the backend API for hub.jw.org/meetings/ by scanning the SPA chunks."""

from __future__ import annotations

import asyncio
import re

import httpx


async def go() -> None:
    async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as c:
        chunks = [
            "chunk-GFS7H2A4",
            "chunk-FQ7EPG54",
            "chunk-RQNX6KLW",
            "chunk-ZWHFJXLM",
            "chunk-NXCHYDR4",
            "chunk-3GYD4EVN",
            "chunk-JIBO5TGK",
            "chunk-XX2OJFC2",
        ]
        for ck in chunks:
            r = await c.get(
                f"https://hub.jw.org/meetings/{ck}.js",
                headers={"User-Agent": "Mozilla/5.0"},
            )
            # Print all URLs discovered.
            urls = set()
            for m in re.finditer(r'https?://[A-Za-z0-9./_:?=%&-]+', r.text):
                u = m.group(0)
                if 'jw' in u.lower() and 'cdn' not in u and 'azure' not in u and 'maps.google' not in u:
                    urls.add(u[:160])
            for u in sorted(urls):
                print(f"{ck}: {u}")
            # Also: any var like "X.apiUrl='...'" or const
            for m in re.finditer(r'[\w.]+\s*=\s*["\'](https?://[^"\']+)["\']', r.text):
                u = m.group(1)
                if 'jw' in u.lower() and 'cdn' not in u and 'azure' not in u:
                    print(f"{ck} CONST: {u}")


asyncio.run(go())
