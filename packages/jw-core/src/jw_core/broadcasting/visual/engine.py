"""End-to-end engine wiring sampler + VLM + CLIP + indexer (Fase 69).

This is the orchestration layer the CLI and MCP call into. It pulls the
defaults from env (with Fake providers as fallback) and writes/reads from
`~/.jw-agent-toolkit/broadcasting/visual/` by default.
"""

from __future__ import annotations

import os
from pathlib import Path

from jw_core.broadcasting.visual.indexer import VisualIndexer
from jw_core.broadcasting.visual.models import (
    IndexStats,
    VisualSearchHit,
)
from jw_core.broadcasting.visual.providers import (
    FakeCLIPEncoder,
    FakeVLMProvider,
)
from jw_core.broadcasting.visual.sampler import (
    fake_sample,
    sample_frames,
)
from jw_core.broadcasting.visual.search import visual_search


def default_root() -> Path:
    """Resolve the index root (env override + xdg default)."""
    override = os.environ.get("JW_VISUAL_INDEX_ROOT")
    if override:
        return Path(override).expanduser()
    return Path("~/.jw-agent-toolkit/broadcasting/visual").expanduser()


def index_video(
    video_path: str | Path,
    *,
    root: Path | None = None,
    interval_s: float = 5.0,
    embedding_dim: int = 64,
    use_real_ffmpeg: bool = True,
    video_id: str | None = None,
) -> IndexStats:
    """Index `video_path` into the visual store.

    Uses Fake VLM + Fake CLIP by default. The real provider stack is wired
    via Plugin SDK F41 in production. With `use_real_ffmpeg=False`, the
    sampler is bypassed and synthetic fake frames are used (testing).
    """
    root = root or default_root()
    vid = video_id or Path(video_path).stem
    idx = VisualIndexer(root, embedding_dim=embedding_dim)
    vlm = FakeVLMProvider()
    clip = FakeCLIPEncoder(embedding_dim=embedding_dim)
    sampler_iter = (
        sample_frames(video_path, interval_s=interval_s)
        if use_real_ffmpeg
        else fake_sample(duration_s=30.0, interval_s=interval_s)
    )
    for ts, image_bytes in sampler_iter:
        caption = vlm.caption(image_bytes, language="en")
        emb = clip.encode_image(image_bytes)
        idx.add_frame(
            video_id=vid,
            timestamp_s=float(ts),
            caption=caption,
            embedding=emb,
        )
    stats = idx.stats()
    idx.close()
    return stats


def search_index(
    query: str,
    *,
    root: Path | None = None,
    embedding_dim: int = 64,
    top_k: int = 10,
    min_score: float = 0.0,
) -> list[VisualSearchHit]:
    root = root or default_root()
    idx = VisualIndexer(root, embedding_dim=embedding_dim)
    clip = FakeCLIPEncoder(embedding_dim=embedding_dim)
    hits = visual_search(
        idx,
        query,
        clip_encoder=clip,
        top_k=top_k,
        min_score=min_score,
    )
    idx.close()
    return hits


def stats_index(
    *, root: Path | None = None, embedding_dim: int = 64
) -> IndexStats:
    root = root or default_root()
    idx = VisualIndexer(root, embedding_dim=embedding_dim)
    stats = idx.stats()
    idx.close()
    return stats
