"""F57 — MediaResolver resuelve MediaRef abstractas a URLs directas."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from jw_meeting_media.media_resolver import MediaResolver
from jw_meeting_media.models import MediaKind, MediaRef


@pytest.mark.asyncio
async def test_resolve_image_passes_through():
    """Imágenes ya tienen URL directa; no requieren resolución."""
    resolver = MediaResolver()
    ref = MediaRef(
        kind=MediaKind.IMAGE,
        title="img",
        url="https://imgp.jw-cdn.org/some.jpg",
    )
    resolved = await resolver.resolve(ref)
    assert resolved.url == ref.url


@pytest.mark.asyncio
async def test_resolve_video_uses_pubmedia():
    """Videos sin URL directa se resuelven vía PubMediaClient."""
    pub_client_mock = MagicMock()
    pub_client_mock.get_publication = AsyncMock(
        return_value={
            "files": {
                "es": {
                    "MP4": [
                        {
                            "file": {"url": "https://download.jw.org/video/example_720p.mp4"},
                            "title": "Example 720p",
                            "filesize": 12345678,
                            "checksum": "abc123",
                        },
                    ],
                },
            },
        }
    )
    resolver = MediaResolver(pub_media_client=pub_client_mock)
    ref = MediaRef(
        kind=MediaKind.VIDEO,
        title="Example",
        url="",
        pub_code="pk",
        track=12,
        language="es",
    )
    resolved = await resolver.resolve(ref)
    assert resolved.url.endswith(".mp4")
    assert resolved.sha256 == "abc123"
