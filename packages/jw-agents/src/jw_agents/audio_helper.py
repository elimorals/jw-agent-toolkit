"""audio_helper agent — high-level audio orchestration for the toolkit.

Three convenience operations:

  - `read_verse_aloud(book_num, chapter, verse)` — fetches the verse,
    synthesises audio in the requested language, returns the file path
    + the verse text and citation.
  - `read_article_aloud(url, max_paragraphs)` — same for article paragraphs.
  - `search_broadcasting(query)` — full-text search against the local
    JW Broadcasting subtitle index.

All three return an `AgentResult` so calling LLMs see structured outputs.
"""

from __future__ import annotations

from pathlib import Path

from jw_core.audio.broadcasting import BroadcastingIndex, deeplink_for_segment
from jw_core.audio.tts import TTSError, synthesize_to_file
from jw_core.clients.wol import WOLClient
from jw_core.parsers.article import parse_article
from jw_core.parsers.verse import get_verse

from jw_agents.base import AgentResult, Citation, Finding


async def read_verse_aloud(
    book_num: int,
    chapter: int,
    verse: int,
    *,
    language: str = "en",
    output_path: str | Path = "verse.wav",
    provider: str | None = None,
    voice: str | None = None,
    wol: WOLClient | None = None,
) -> AgentResult:
    """Fetch a verse and synthesise it to an audio file."""
    result = AgentResult(query=f"{book_num}:{chapter}:{verse}", agent_name="read_verse_aloud")
    owned = wol is None
    wol = wol or WOLClient()
    try:
        url, html = await wol.get_bible_chapter(book_num, chapter, language=language)
        verse_obj = get_verse(html, book_num, chapter, verse, language=language)
    finally:
        if owned:
            await wol.aclose()

    if verse_obj is None:
        result.warnings.append(f"Verse {book_num}:{chapter}:{verse} not found")
        return result

    try:
        path = synthesize_to_file(
            verse_obj.text,
            output_path,
            language=language,
            voice=voice,
            provider=provider,
        )
    except TTSError as e:
        result.warnings.append(f"TTS failed: {e}")
        return result

    result.findings.append(
        Finding(
            summary=f"Audio for {verse_obj.book_num}:{verse_obj.chapter}:{verse_obj.verse}",
            excerpt=verse_obj.text,
            citation=Citation(url=verse_obj.wol_url(), title="Verse audio", kind="audio"),
            metadata={"source": "tts_verse", "audio_path": str(path)},
        )
    )
    return result


async def read_article_aloud(
    url: str,
    *,
    output_path: str | Path = "article.wav",
    language: str = "en",
    max_paragraphs: int = 5,
    provider: str | None = None,
    voice: str | None = None,
    wol: WOLClient | None = None,
) -> AgentResult:
    result = AgentResult(query=url, agent_name="read_article_aloud")
    owned = wol is None
    wol = wol or WOLClient()
    try:
        html = await wol.fetch(url)
    finally:
        if owned:
            await wol.aclose()

    article = parse_article(html)
    text = "\n\n".join(article.paragraphs[:max_paragraphs])
    if not text:
        result.warnings.append("Article had no paragraphs")
        return result
    try:
        path = synthesize_to_file(
            text,
            output_path,
            language=language,
            voice=voice,
            provider=provider,
        )
    except TTSError as e:
        result.warnings.append(f"TTS failed: {e}")
        return result

    result.findings.append(
        Finding(
            summary=f"Audio for {article.title or 'article'}",
            excerpt=text[:500],
            citation=Citation(url=url, title=article.title, kind="audio"),
            metadata={"source": "tts_article", "audio_path": str(path), "paragraphs": max_paragraphs},
        )
    )
    return result


def search_broadcasting(
    query: str,
    *,
    language: str | None = None,
    top_k: int = 10,
    index_path: str | Path | None = None,
) -> AgentResult:
    """Full-text search over the JW Broadcasting subtitle index."""
    result = AgentResult(query=query, agent_name="search_broadcasting")
    with BroadcastingIndex(index_path) as idx:
        try:
            hits = idx.search(query, language=language, top_k=top_k)
        except Exception as e:
            result.warnings.append(f"FTS query failed: {e}")
            return result
        stats = idx.stats()
    result.metadata["index_stats"] = stats
    for hit in hits:
        deeplink = deeplink_for_segment(hit.get("source_url", ""), hit["start"])
        result.findings.append(
            Finding(
                summary=f"{hit['title'] or hit['video_id']} @ {hit['start']:.0f}s",
                excerpt=hit["text"],
                citation=Citation(
                    url=deeplink,
                    title=hit["title"] or hit["video_id"],
                    kind="broadcasting_segment",
                    metadata={"start": hit["start"], "end": hit["end"]},
                ),
                metadata={"source": "broadcasting_segment"},
            )
        )
    return result
