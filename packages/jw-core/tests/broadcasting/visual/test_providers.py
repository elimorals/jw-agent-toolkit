"""VLM + CLIP provider tests (Fase 69)."""

from __future__ import annotations

import math

from jw_core.broadcasting.visual.providers import (
    CLIPEncoder,
    FakeCLIPEncoder,
    FakeVLMProvider,
    VLMProvider,
)


def test_fake_vlm_is_a_VLMProvider() -> None:
    assert isinstance(FakeVLMProvider(), VLMProvider)


def test_fake_clip_is_a_CLIPEncoder() -> None:
    assert isinstance(FakeCLIPEncoder(), CLIPEncoder)


def test_fake_vlm_caption_is_deterministic() -> None:
    vlm = FakeVLMProvider()
    a = vlm.caption(b"hello", "en")
    b = vlm.caption(b"hello", "en")
    assert a == b
    assert a.startswith("image-")
    assert a.endswith("(en)")


def test_fake_vlm_caption_changes_with_language() -> None:
    vlm = FakeVLMProvider()
    en = vlm.caption(b"x", "en")
    es = vlm.caption(b"x", "es")
    assert en != es


def test_fake_clip_image_embedding_has_correct_dim() -> None:
    clip = FakeCLIPEncoder(embedding_dim=128)
    v = clip.encode_image(b"x")
    assert len(v) == 128


def test_fake_clip_image_embedding_is_unit_normalized() -> None:
    clip = FakeCLIPEncoder(embedding_dim=64)
    v = clip.encode_image(b"x")
    norm = math.sqrt(sum(x * x for x in v))
    assert abs(norm - 1.0) < 1e-6


def test_fake_clip_text_image_embeddings_are_deterministic() -> None:
    clip = FakeCLIPEncoder()
    assert clip.encode_text("alpha") == clip.encode_text("alpha")
    assert clip.encode_text("alpha") != clip.encode_text("beta")
