"""End-to-end live test of Phase 3 tools against real wol.jw.org."""
import asyncio

from jw_agents import verse_explainer
from jw_core.clients.wol import WOLClient
from jw_core.parsers.study_notes import (
    parse_cross_references,
    parse_study_notes,
)
from jw_core.parsers.verse import get_verse


async def main() -> None:
    wol = WOLClient()
    try:
        # 1. Live: fetch John 3 in English
        print("=== Fetching John 3 (nwtsty, en) ===")
        url, html = await wol.get_bible_chapter(43, 3, language="en")
        print(f"  URL: {url}")
        print(f"  HTML bytes: {len(html):,}")

        # 2. Parse verse 16
        v = get_verse(html, 43, 3, 16)
        print(f"\n=== get_verse(43, 3, 16) ===")
        print(f"  text: {v.text[:120]}...")
        print(f"  wol_url: {v.wol_url()[:80]}")

        # 3. Study notes for verse 16
        notes = parse_study_notes(html, book_num=43, chapter=3)
        v16_notes = [n for n in notes if n.verse == 16]
        print(f"\n=== Study notes ===")
        print(f"  total notes in chapter: {len(notes)}")
        print(f"  notes mapped to v16: {len(v16_notes)}")
        if v16_notes:
            print(f"  first v16 note: {v16_notes[0].headword!r}")
            print(f"    body[:120]: {v16_notes[0].body[:120]}...")

        # 4. Cross-refs for verse 16
        xrefs = parse_cross_references(html, book_num=43, chapter=3)
        v16_xrefs = [x for x in xrefs if x.verse == 16]
        print(f"\n=== Cross-references ===")
        print(f"  total xrefs in chapter: {len(xrefs)}")
        print(f"  xrefs in v16: {len(v16_xrefs)}")
        if v16_xrefs:
            print(f"  v16 xref href: {v16_xrefs[0].href[:80]}")

        # 5. verse_explainer agent end-to-end
        print(f"\n=== verse_explainer('John 3:16') ===")
        result = await verse_explainer("John 3:16", language="en", wol=wol)
        kinds = [f.metadata.get("kind") for f in result.findings]
        from collections import Counter
        print(f"  findings count: {len(result.findings)}")
        print(f"  by kind: {Counter(kinds)}")
        target = [f for f in result.findings if f.metadata.get("kind") == "target_verse"]
        if target:
            print(f"  target verse text: {target[0].excerpt[:80]}...")
        study = [f for f in result.findings if f.metadata.get("kind") == "study_note"]
        if study:
            print(f"  first study note: {study[0].summary}")
    finally:
        await wol.aclose()


asyncio.run(main())
