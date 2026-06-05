"""F57 — Thumbnailer para imagen y video (ffmpeg)."""

from __future__ import annotations

import pytest

pytest.importorskip("PIL", reason="Pillow not installed (extras [thumbnails])")

from jw_meeting_media.thumbnailer import Thumbnailer  # noqa: E402


@pytest.fixture()
def thumbnailer(tmp_path) -> Thumbnailer:
    return Thumbnailer(cache_root=tmp_path / "thumbs")


def test_thumbnail_jpeg(thumbnailer, tmp_path):
    from PIL import Image

    img_path = tmp_path / "source.jpg"
    Image.new("RGB", (800, 600), color="red").save(img_path, "JPEG")

    thumb_path = thumbnailer.for_image(img_path, max_size=200)
    assert thumb_path.exists()
    with Image.open(thumb_path) as t:
        assert max(t.size) <= 200


def test_thumbnail_idempotent(thumbnailer, tmp_path):
    from PIL import Image

    img_path = tmp_path / "source.jpg"
    Image.new("RGB", (800, 600), color="blue").save(img_path, "JPEG")

    thumb1 = thumbnailer.for_image(img_path, max_size=200)
    mtime1 = thumb1.stat().st_mtime
    thumb2 = thumbnailer.for_image(img_path, max_size=200)
    assert thumb1 == thumb2
    assert mtime1 == thumb2.stat().st_mtime  # no regenerated
