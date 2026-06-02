"""Cutoff/threshold logic for the synth judge.

JudgeMode is the user-facing knob (off/loose/strict). Each mode maps to a
default `overall` cutoff and a default policy for "require NLI verdict ==
entails". Recipes can override either independently.
"""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel


class JudgeMode(str, Enum):
    """User-facing operating mode for the judge."""

    OFF = "off"
    LOOSE = "loose"
    STRICT = "strict"


DEFAULT_CUTOFFS: dict[JudgeMode, float | None] = {
    JudgeMode.OFF: None,
    JudgeMode.LOOSE: 5.0,
    JudgeMode.STRICT: 6.5,
}

_DEFAULT_REQUIRE_NLI_ENTAILS: dict[JudgeMode, bool] = {
    JudgeMode.OFF: False,
    JudgeMode.LOOSE: False,
    JudgeMode.STRICT: True,
}


class JudgeOverrides(BaseModel):
    """Optional overrides from a recipe YAML.

    All fields are None when not set — `resolve_*` returns the mode default.
    """

    overall_cutoff: float | None = None
    require_nli_entails: bool | None = None


def resolve_cutoff(mode: JudgeMode, overrides: JudgeOverrides) -> float | None:
    """Return the effective overall cutoff for a mode + overrides combo.

    OFF always wins: even with an override, OFF means "no judge".
    """

    if mode == JudgeMode.OFF:
        return None
    if overrides.overall_cutoff is not None:
        return overrides.overall_cutoff
    return DEFAULT_CUTOFFS[mode]


def resolve_require_nli_entails(
    mode: JudgeMode, overrides: JudgeOverrides
) -> bool:
    """Return whether to require NLI=entails for keeping a pair."""

    if overrides.require_nli_entails is not None:
        return overrides.require_nli_entails
    return _DEFAULT_REQUIRE_NLI_ENTAILS[mode]
