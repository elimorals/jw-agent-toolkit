"""Locate the docid of 'Religions, Customs, and Beliefs' and download as fixture."""
import asyncio
import re
from pathlib import Path

import httpx

from jw_core.clients.cdn import CDNClient


async def main() -> None:
    print("Searching for 'Religions, Customs, and Beliefs'...")
    cdn = CDNClient()
    try:
        # First find the docid
        data = await cdn.search(
            "Religions Customs and Beliefs", filter_type="indexes",
            language="E", limit=10,
        )
        candidates: list[dict] = []
        for r in data.get("results", []):
            if not isinstance(r, dict):
                continue
            if r.get("type") == "group":
                candidates.extend(x for x in r.get("results", []) if isinstance(x, dict))
            else:
                candidates.append(r)

        target_docid = None
        target_url = None
        for c in candidates:
            url = (c.get("links") or {}).get("wol") or ""
            title = c.get("title", "")
            print(f"  candidate: {title!r}  url={url[:80]}")
            if "religions" in title.lower() and "customs" in title.lower():
                # Extract docid from query param or path
                m = re.search(r"docid=(\d+)|/d/[^/]+/[^/]+/(\d+)", url)
                if m:
                    target_docid = m.group(1) or m.group(2)
                    target_url = url
                    break

        if not target_docid:
            print("\nDid not find a clean 'Religions' subject; using first candidate with docid")
            for c in candidates:
                url = (c.get("links") or {}).get("wol") or ""
                m = re.search(r"docid=(\d+)|/d/[^/]+/[^/]+/(\d+)", url)
                if m:
                    target_docid = m.group(1) or m.group(2)
                    target_url = url
                    break

        if not target_docid:
            print("Could not find any docid")
            return

        print(f"\nFetching subject docid={target_docid}")
        fetch_url = f"https://wol.jw.org/en/wol/d/r1/lp-e/{target_docid}"
        async with httpx.AsyncClient(
            timeout=60.0, follow_redirects=True,
            headers={"User-Agent": "Mozilla/5.0", "Accept-Language": "en"},
        ) as c:
            r = await c.get(fetch_url)
            r.raise_for_status()
            dest = Path(f"packages/jw-core/tests/fixtures/wt_pub_index_alt_{target_docid}.html")
            dest.write_text(r.text, encoding="utf-8")
            print(f"  Saved {len(r.text):,} bytes → {dest.name}")
            print(f"  Final URL: {r.url}")
    finally:
        await cdn.aclose()


asyncio.run(main())
