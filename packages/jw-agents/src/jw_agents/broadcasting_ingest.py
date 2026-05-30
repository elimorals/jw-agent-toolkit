"""broadcasting_ingest agent — discover, download and index JW Broadcasting.

End-to-end pipeline:

  1. Walk the mediator category tree for `language`.
  2. For each video with subtitles, download the VTT to disk cache.
  3. Index the parsed segments into `BroadcastingIndex` (FTS5).

Returns an `AgentResult` summarising how many videos were processed.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path

from jw_core.audio.broadcasting import BroadcastingIndex, index_vtt_file
from jw_core.clients.jw_broadcasting import JWBroadcastingClient

from jw_agents.base import AgentResult, Citation, Finding

logger = logging.getLogger(__name__)


def _subtitles_cache_dir() -> Path:
    p = Path(os.getenv("JW_VTT_CACHE", "~/.jw-agent-toolkit/vtt/")).expanduser()
    p.mkdir(parents=True, exist_ok=True)
    return p


async def broadcasting_ingest(
    *,
    language: str = "en",
    root_category: str = "VideoOnDemand",
    max_depth: int = 3,
    max_videos: int = 50,
    client: JWBroadcastingClient | None = None,
    index_path: str | Path | None = None,
) -> AgentResult:
    """Discover + download + index JW Broadcasting subtitles."""
    result = AgentResult(query=root_category, agent_name="broadcasting_ingest")
    result.metadata.update({"language": language, "root_category": root_category})

    owned = client is None
    client = client or JWBroadcastingClient()
    cache = _subtitles_cache_dir()

    try:
        videos = await client.discover_all_videos(
            language=language, root=root_category, max_depth=max_depth, limit=max_videos
        )
    except Exception as e:
        result.warnings.append(f"Discovery failed: {e}")
        videos = []
    result.metadata["discovered_videos"] = len(videos)

    indexed = 0
    skipped = 0
    try:
        with BroadcastingIndex(index_path) as idx:
            for video in videos:
                if not video.subtitle_url:
                    skipped += 1
                    continue
                vtt_path = cache / f"{video.guid or video.natural_key}.vtt"
                if not vtt_path.exists():
                    try:
                        await client.download_subtitle(video, vtt_path)
                    except Exception as e:
                        result.warnings.append(f"VTT download failed for {video.guid}: {e}")
                        skipped += 1
                        continue
                try:
                    n_segs = index_vtt_file(
                        idx,
                        vtt_path,
                        video_id=video.guid or video.natural_key,
                        title=video.title,
                        language=language,
                        source_url=video.download_url or video.subtitle_url,
                    )
                except Exception as e:
                    result.warnings.append(f"VTT index failed for {video.guid}: {e}")
                    skipped += 1
                    continue
                indexed += 1
                result.findings.append(
                    Finding(
                        summary=f"Indexed: {video.title}",
                        excerpt=f"{n_segs} segments · {video.duration_seconds:.0f}s",
                        citation=Citation(
                            url=video.download_url or video.subtitle_url,
                            title=video.title,
                            kind="broadcasting_video",
                            metadata={"guid": video.guid, "natural_key": video.natural_key},
                        ),
                        metadata={"source": "broadcasting_ingest", "segments": n_segs},
                    )
                )
            stats = idx.stats()
    finally:
        if owned:
            await client.aclose()

    result.metadata.update({"indexed": indexed, "skipped": skipped, "index_stats": stats})
    return result
