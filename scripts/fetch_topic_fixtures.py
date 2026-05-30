"""Download Watch Tower Publications Index pages for offline parser dev."""
import asyncio
from pathlib import Path

import httpx

FIXTURES = Path("packages/jw-core/tests/fixtures")
FIXTURES.mkdir(parents=True, exist_ok=True)

PAGES = {
    "wt_pub_index_home.html": "https://wol.jw.org/en/wol/d/r1/lp-e/1200276168",
    "wt_pub_index_trinity.html": "https://wol.jw.org/en/wol/d/r1/lp-e/1200275936",
    "wt_research_guide.html": "https://wol.jw.org/en/wol/d/r1/lp-e/1200277232",
}


async def main() -> None:
    async with httpx.AsyncClient(
        timeout=60.0,
        follow_redirects=True,
        headers={"User-Agent": "Mozilla/5.0", "Accept-Language": "en"},
    ) as c:
        for name, url in PAGES.items():
            try:
                r = await c.get(url)
                r.raise_for_status()
                dest = FIXTURES / name
                dest.write_text(r.text, encoding="utf-8")
                print(f"  ✓ {name}  ({len(r.text):,} bytes)  ← {url}")
            except Exception as e:
                print(f"  ✗ {name}  FAILED: {type(e).__name__}: {e}")


asyncio.run(main())
