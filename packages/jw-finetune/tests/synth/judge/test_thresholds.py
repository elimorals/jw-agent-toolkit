"""Threshold + mode resolution tests."""

from __future__ import annotations

import pytest
from jw_finetune.synth.judge.thresholds import (
    DEFAULT_CUTOFFS,
    JudgeMode,
    JudgeOverrides,
    resolve_cutoff,
    resolve_require_nli_entails,
)


def test_judge_mode_values() -> None:
    assert JudgeMode.OFF.value == "off"
    assert JudgeMode.LOOSE.value == "loose"
    assert JudgeMode.STRICT.value == "strict"


def test_default_cutoffs_table() -> None:
    assert DEFAULT_CUTOFFS[JudgeMode.OFF] is None
    assert DEFAULT_CUTOFFS[JudgeMode.LOOSE] == 5.0
    assert DEFAULT_CUTOFFS[JudgeMode.STRICT] == 6.5


def test_resolve_cutoff_uses_default_when_no_override() -> None:
    assert resolve_cutoff(JudgeMode.LOOSE, JudgeOverrides()) == 5.0
    assert resolve_cutoff(JudgeMode.STRICT, JudgeOverrides()) == 6.5
    assert resolve_cutoff(JudgeMode.OFF, JudgeOverrides()) is None


def test_resolve_cutoff_respects_overall_cutoff_override() -> None:
    ov = JudgeOverrides(overall_cutoff=7.0)
    assert resolve_cutoff(JudgeMode.LOOSE, ov) == 7.0
    assert resolve_cutoff(JudgeMode.STRICT, ov) == 7.0


def test_resolve_cutoff_off_mode_ignores_override() -> None:
    ov = JudgeOverrides(overall_cutoff=7.0)
    assert resolve_cutoff(JudgeMode.OFF, ov) is None


def test_resolve_require_nli_entails_defaults() -> None:
    assert resolve_require_nli_entails(JudgeMode.OFF, JudgeOverrides()) is False
    assert (
        resolve_require_nli_entails(JudgeMode.LOOSE, JudgeOverrides()) is False
    )
    assert (
        resolve_require_nli_entails(JudgeMode.STRICT, JudgeOverrides()) is True
    )


def test_resolve_require_nli_entails_override() -> None:
    ov = JudgeOverrides(require_nli_entails=False)
    assert resolve_require_nli_entails(JudgeMode.STRICT, ov) is False
    ov2 = JudgeOverrides(require_nli_entails=True)
    assert resolve_require_nli_entails(JudgeMode.LOOSE, ov2) is True


def test_judge_mode_from_string_case_insensitive() -> None:
    assert JudgeMode("loose") == JudgeMode.LOOSE
    assert JudgeMode("STRICT".lower()) == JudgeMode.STRICT
    with pytest.raises(ValueError):
        JudgeMode("bogus")
