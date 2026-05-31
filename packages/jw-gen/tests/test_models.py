"""Tests for jw_gen.models."""

from __future__ import annotations

from pathlib import Path

import pytest
from jw_gen.models import (
    CostHint,
    GenerationRequest,
    GenerationResult,
    Language,
    SafetyDecision,
    WatermarkConfig,
)


def test_watermark_config_defaults_to_visible_plus_metadata() -> None:
    cfg = WatermarkConfig()
    assert cfg.mode == "visible+metadata"
    assert cfg.opacity == 0.4
    assert cfg.text_template_key == "watermark.default"


def test_watermark_config_rejects_unknown_mode() -> None:
    with pytest.raises(ValueError):
        WatermarkConfig(mode="invisible-supersecret")  # type: ignore[arg-type]


def test_generation_request_normalizes_lang_lowercase() -> None:
    req = GenerationRequest(prompt="a", kind="image", lang="ES")
    assert req.lang == "es"


def test_generation_request_rejects_unknown_kind() -> None:
    with pytest.raises(ValueError):
        GenerationRequest(prompt="a", kind="hologram", lang="en")  # type: ignore[arg-type]


def test_generation_request_lang_default_is_es() -> None:
    req = GenerationRequest(prompt="hola", kind="image")
    assert req.lang == "es"


def test_safety_decision_pass_has_no_reason() -> None:
    d = SafetyDecision(allow=True, augmented_prompt=None, audit_flags={})
    assert d.allow is True
    assert d.reason is None


def test_safety_decision_refuse_carries_i18n_key() -> None:
    d = SafetyDecision(allow=False, reason="safety.refuse.logo", audit_flags={"logo_check": "fail"})
    assert d.allow is False
    assert d.reason == "safety.refuse.logo"


def test_generation_result_path_field_populated(tmp_path: Path) -> None:
    out = tmp_path / "x.png"
    out.write_bytes(b"x")
    result = GenerationResult(
        output_path=out,
        disclaimer_path=tmp_path / "x.png.disclaimer.txt",
        provider="fake",
        kind="image",
        watermark_mode="visible+metadata",
        prompt_sha256="abc",
        audit_id="evt-1",
    )
    assert result.output_path == out


def test_cost_hint_defaults_to_zero() -> None:
    c = CostHint()
    assert c.usd == 0.0
    assert c.time_s == 0.0


def test_language_literal_values() -> None:
    # Compile-time only; runtime check just confirms the alias is importable.
    _: Language = "es"
    _ = "en"  # type: ignore[assignment]
    _ = "pt"  # type: ignore[assignment]
