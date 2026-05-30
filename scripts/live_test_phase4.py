"""End-to-end live test: topic index search → subject page → apologetics."""
import asyncio
from collections import Counter

from jw_agents import apologetics
from jw_core.clients.topic_index import TopicIndexClient


async def main() -> None:
    print("=" * 70)
    print("Topic Index: search_subjects('Trinity')")
    print("=" * 70)
    client = TopicIndexClient()
    try:
        subjects = await client.search_subjects("Trinity", language="E", limit=5)
        for s in subjects[:5]:
            print(f"  • {s['title']!r:<60} docid={s['docid']!r}")
            print(f"    url: {s['wol_url'][:80]}")

        if subjects:
            print()
            print("=" * 70)
            print(f"Topic Index: get_subject_page(docid={subjects[0]['docid']!r})")
            print("=" * 70)
            subject = await client.get_subject_page(subjects[0]['docid'], language='en')
            print(f"  title: {subject.title}")
            print(f"  total subheadings: {len(subject.subheadings)}")
            print(f"  total citations: {subject.total_citations}")
            print(f"  see_also: {subject.see_also[:3]}")
            print(f"  top 5 subheadings:")
            for sh in subject.subheadings[:5]:
                cit_count = len(sh.citations)
                level = "top" if sh.is_top_level else "sub"
                print(f"    [{level}] {sh.heading[:60]!r}  citations={cit_count}")

        print()
        print("=" * 70)
        print("apologetics('What does the Bible teach about the Trinity?')")
        print("=" * 70)
        r = await apologetics(
            "What does the Bible teach about the Trinity?",
            language="E", topic_top_k=1, topic_subheadings_limit=3, web_top_k=2,
        )
        sources = Counter(f.metadata.get("source") for f in r.findings)
        print(f"  total findings: {len(r.findings)}")
        print(f"  by source: {dict(sources)}")
        print(f"  warnings: {r.warnings}")
        print()
        print("  topic_index findings (the Phase 4 enrichment):")
        for f in r.findings:
            if f.metadata.get("source", "").startswith("topic_index"):
                print(f"    - {f.summary[:80]}")
                if f.excerpt:
                    print(f"      excerpt: {f.excerpt[:100]}")
    finally:
        await client.aclose()


asyncio.run(main())
