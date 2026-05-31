from __future__ import annotations

import hashlib
from pathlib import Path

import pytest
from jw_gen.models import GenerationRequest, WatermarkConfig
from jw_gen.policy import (
    PolicyError,
    apply_watermark,
    assert_personal_use,
    embed_metadata,
    finalize_output,
    write_disclaimer_sibling,
)
from PIL import Image


def _make_png(path: Path, w: int = 200, h: int = 200) -> Path:
    img = Image.new("RGB", (w, h), color=(255, 255, 255))
    img.save(path, format="PNG")
    return path


def test_apply_watermark_adds_visible_text(tmp_path: Path) -> None:
    src = _make_png(tmp_path / "raw.png")
    out = apply_watermark(src, text="jw-gen · uso personal", cfg=WatermarkConfig())
    assert out.exists()
    img = Image.open(out).convert("RGB")
    # Scan the watermark band for any non-white pixel — proves a rasterized mark landed.
    anchor_y = int(0.93 * img.height)
    found_mark = False
    for y in range(anchor_y, min(img.height, anchor_y + 30)):
        for x in range(0, img.width, 2):
            if img.getpixel((x, y)) != (255, 255, 255):
                found_mark = True
                break
        if found_mark:
            break
    assert found_mark, "watermark did not produce any visible pixels in the anchor band"


def test_embed_metadata_writes_exif(tmp_path: Path) -> None:
    src = _make_png(tmp_path / "raw.png")
    embed_metadata(
        src,
        fields={
            "Software": "jw-gen",
            "ImageDescription": "personal-use illustration",
            "prompt_sha256": "abc",
            "provider": "fake",
        },
    )
    raw = src.read_bytes()
    assert b"jw-gen" in raw


def test_write_disclaimer_sibling_writes_localized(tmp_path: Path) -> None:
    target = tmp_path / "out.png"
    target.write_bytes(b"x")
    disclaimer = write_disclaimer_sibling(
        target=target,
        lang="es",
        prompt_sha256="abc",
        provider="fake",
        watermark_mode="visible+metadata",
        realistic_optin=False,
    )
    assert disclaimer.exists()
    text = disclaimer.read_text(encoding="utf-8")
    assert "uso personal" in text.lower()
    assert "abc" in text


def test_write_disclaimer_sibling_includes_realism_warning_when_optin(tmp_path: Path) -> None:
    target = tmp_path / "out.png"
    target.write_bytes(b"x")
    disclaimer = write_disclaimer_sibling(
        target=target,
        lang="en",
        prompt_sha256="def",
        provider="fake",
        watermark_mode="visible+metadata",
        realistic_optin=True,
    )
    text = disclaimer.read_text(encoding="utf-8")
    assert "realistic" in text.lower()


def test_assert_personal_use_allows_jw_gen_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("JW_GEN_HOME", str(tmp_path / ".jw-gen"))
    assert_personal_use(tmp_path / ".jw-gen" / "out.png")


def test_assert_personal_use_warns_on_dropbox_path(tmp_path: Path) -> None:
    warning = assert_personal_use(tmp_path / "Dropbox" / "out.png")
    assert warning is not None
    assert "dropbox" in warning.lower()


def test_finalize_output_complete_path(tmp_path: Path, isolated_jw_gen_home: Path) -> None:
    raw = _make_png(tmp_path / "raw.png")
    req = GenerationRequest(prompt="ilustración pacífica", kind="image", lang="es")
    result = finalize_output(
        raw_path=raw,
        request=req,
        dest=tmp_path / "out.png",
        provider="fake",
    )
    assert result.output_path.exists()
    assert result.disclaimer_path.exists()
    assert result.watermark_mode == "visible+metadata"
    assert result.prompt_sha256 == hashlib.sha256(req.prompt.encode()).hexdigest()


def test_finalize_output_failclosed_when_disclaimer_fails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, isolated_jw_gen_home: Path
) -> None:
    raw = _make_png(tmp_path / "raw.png")
    req = GenerationRequest(prompt="ilustración pacífica", kind="image", lang="es")

    def boom(*_args: object, **_kwargs: object) -> Path:
        raise OSError("disclaimer broken")

    monkeypatch.setattr("jw_gen.policy.write_disclaimer_sibling", boom)
    with pytest.raises(PolicyError):
        finalize_output(raw_path=raw, request=req, dest=tmp_path / "out.png", provider="fake")
    assert not (tmp_path / "out.png").exists()


def test_finalize_output_failclosed_when_watermark_fails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, isolated_jw_gen_home: Path
) -> None:
    raw = _make_png(tmp_path / "raw.png")
    req = GenerationRequest(prompt="ilustración pacífica", kind="image", lang="es")

    def boom(*_args: object, **_kwargs: object) -> Path:
        raise OSError("watermark broken")

    monkeypatch.setattr("jw_gen.policy.apply_watermark", boom)
    with pytest.raises(PolicyError):
        finalize_output(raw_path=raw, request=req, dest=tmp_path / "out.png", provider="fake")
    assert not (tmp_path / "out.png").exists()
