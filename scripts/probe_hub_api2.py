"""Deeper hub.jw.org chunk inspection."""

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
            text = r.text
            # search context around "meetingType" — should reveal call site.
            for m in re.finditer(r'.{200}meetingType.{200}', text):
                print(f"=== {ck} ===")
                print(m.group(0))
                print()


asyncio.run(go())
