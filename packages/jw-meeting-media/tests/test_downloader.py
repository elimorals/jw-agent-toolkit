"""F57 — Downloader con idempotencia por sha256 y cache local."""

from __future__ import annotations

import hashlib
from pathlib import Path

import pytest
from jw_meeting_media.downloader import Downloader
from jw_meeting_media.models import MediaKind, MediaRef


@pytest.fixture()
def cache_root(tmp_path) -> Path:
    return tmp_path / "meetings_cache"


@pytest.mark.asyncio
async def test_download_writes_to_cache(httpx_mock, cache_root):
    content = b"fake-jpeg-bytes" * 100
    expected_sha = hashlib.sha256(content).hexdigest()
    httpx_mock.add_response(
        url="https://imgp.jw-cdn.org/test.jpg",
        content=content,
    )

    dl = Downloader(cache_root=cache_root)
    ref = MediaRef(
        kind=MediaKind.IMAGE,
        title="t",
        url="https://imgp.jw-cdn.org/test.jpg",
        sha256=expected_sha,
        language="es",
    )
    local = await dl.download(ref, language="es", year=2026, week=23)
    assert local.exists()
    assert local.read_bytes() == content


@pytest.mark.asyncio
async def test_download_skips_if_sha256_matches(httpx_mock, cache_root):
    """Re-download con archivo cacheado válido no hace HTTP."""
    content = b"data" * 100
    expected_sha = hashlib.sha256(content).hexdigest()

    target_dir = cache_root / "es" / "2026" / "23"
    target_dir.mkdir(parents=True)
    cached_file = target_dir / "abc.jpg"
    cached_file.write_bytes(content)

    dl = Downloader(cache_root=cache_root)
    ref = MediaRef(
        kind=MediaKind.IMAGE,
        title="t",
        url="https://imgp.jw-cdn.org/abc.jpg",
        sha256=expected_sha,
        language="es",
    )
    local = await dl.download(ref, language="es", year=2026, week=23)
    assert local == cached_file
    assert len(httpx_mock.get_requests()) == 0


@pytest.mark.asyncio
async def test_download_redownloads_if_sha_mismatch(httpx_mock, cache_root):
    """Si el archivo cacheado tiene sha distinto, re-descarga."""
    good_content = b"good" * 100
    bad_content = b"corrupted"
    expected_sha = hashlib.sha256(good_content).hexdigest()

    target_dir = cache_root / "es" / "2026" / "23"
    target_dir.mkdir(parents=True)
    cached_file = target_dir / "xyz.jpg"
    cached_file.write_bytes(bad_content)

    httpx_mock.add_response(
        url="https://imgp.jw-cdn.org/xyz.jpg", content=good_content,
    )

    dl = Downloader(cache_root=cache_root)
    ref = MediaRef(
        kind=MediaKind.IMAGE, title="t",
        url="https://imgp.jw-cdn.org/xyz.jpg", sha256=expected_sha, language="es",
    )
    local = await dl.download(ref, language="es", year=2026, week=23)
    assert local.read_bytes() == good_content


@pytest.mark.asyncio
async def test_download_without_sha_uses_url_basename(httpx_mock, cache_root):
    """Sin sha256, el archivo se cachea por basename de URL."""
    content = b"x" * 10
    httpx_mock.add_response(url="https://example.com/foo.png", content=content)
    dl = Downloader(cache_root=cache_root)
    ref = MediaRef(
        kind=MediaKind.IMAGE, title="t",
        url="https://example.com/foo.png", sha256=None, language="es",
    )
    local = await dl.download(ref, language="es", year=2026, week=23)
    assert local.name == "foo.png"
    assert local.read_bytes() == content
