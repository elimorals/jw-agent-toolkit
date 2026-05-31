"""Pydantic models for jw-gen.

Public types:
    Language                 — Literal["en", "es", "pt"]
    Kind                     — Literal["image", "audio", "video"]
    Target                   — Literal["api", "nvidia", "mlx", "cpu"]
    WatermarkConfig          — controls visible + metadata behavior
    GenerationRequest        — input to providers and policy
    GenerationResult         — what callers see after finalize_output
    SafetyDecision           — output of safety.evaluate
    CostHint                 — provider-supplied price + time estimate

Design notes
------------
* `WatermarkConfig.mode` defaults to "visible+metadata". The only ways to
  weaken it are via explicit CLI `--no-visible-watermark` (drops to
  "metadata-only" and logs to audit) or `--no-watermark` (drops to "off",
  forbidden over MCP entirely).
* `GenerationRequest.lang` is lowercase-normalized — provider templates
  and i18n lookups assume lower case.
* `SafetyDecision.augmented_prompt` is what the safety layer would prefer
  the provider see (e.g. anti-realism suffix appended). When `allow=False`
  the caller MUST short-circuit without invoking the provider.
"""

from __future__ import annotations

from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field, field_validator

Language = Literal["en", "es", "pt"]
Kind = Literal["image", "audio", "video"]
Target = Literal["api", "nvidia", "mlx", "cpu"]
WatermarkMode = Literal["visible+metadata", "metadata-only", "off"]


class WatermarkConfig(BaseModel):
    """Watermark policy carried per-request."""

    mode: WatermarkMode = "visible+metadata"
    opacity: float = Field(default=0.4, ge=0.0, le=1.0)
    text_template_key: str = "watermark.default"
    # Pixel anchor: ratio of width/height from top-left.
    anchor_x: float = Field(default=0.02, ge=0.0, le=1.0)
    anchor_y: float = Field(default=0.93, ge=0.0, le=1.0)


class GenerationRequest(BaseModel):
    """One generation request, before safety + provider routing."""

    prompt: str
    kind: Kind
    lang: Language = "es"
    size: str | None = None  # e.g. "1024x1024" for image, "30s" for audio
    duration_s: float | None = None
    style: str | None = None  # e.g. "illustration", "painterly"
    voice_clone_source: Path | None = None  # if --voice-clone was passed
    realistic_people_optin: bool = False
    watermark: WatermarkConfig = Field(default_factory=WatermarkConfig)
    extra: dict[str, object] = Field(default_factory=dict)

    @field_validator("lang", mode="before")
    @classmethod
    def _lower(cls, v: object) -> object:
        if isinstance(v, str):
            return v.lower()
        return v


class GenerationResult(BaseModel):
    """What callers receive after `policy.finalize_output(...)` succeeds."""

    output_path: Path
    disclaimer_path: Path
    provider: str
    kind: Kind
    watermark_mode: WatermarkMode
    prompt_sha256: str
    audit_id: str
    warnings: list[str] = Field(default_factory=list)


class SafetyDecision(BaseModel):
    """Outcome of `safety.evaluate(...)`."""

    allow: bool
    augmented_prompt: str | None = None
    reason: str | None = None  # i18n key when allow=False
    audit_flags: dict[str, str] = Field(default_factory=dict)


class CostHint(BaseModel):
    """Cost + time estimate from a provider before generation runs."""

    usd: float = 0.0
    time_s: float = 0.0
    notes: str | None = None
