"""Tests for the system-metrics collector."""

from __future__ import annotations

from jw_finetune.monitor import metrics as m


def test_collect_returns_systemmetrics() -> None:
    sm = m.collect()
    d = sm.to_dict()
    # All keys present; values may be None when backend is missing.
    expected_keys = {
        "cpu_percent", "ram_used_mb", "ram_total_mb",
        "gpu_name", "gpu_mem_used_mb", "gpu_mem_total_mb",
        "gpu_util_percent", "gpu_kind",
    }
    assert expected_keys <= set(d.keys())


def test_psutil_returns_tuple_or_nones() -> None:
    cpu, used, total = m._try_psutil()
    # psutil is installed via [monitor] extra (which we have)
    # but tolerate either branch.
    if cpu is not None:
        assert isinstance(cpu, float)
        assert isinstance(used, float)
        assert isinstance(total, float)
        assert total > 0


def test_nvidia_returns_none_or_dict() -> None:
    g = m._try_nvidia()
    assert g is None or isinstance(g, dict)
    if isinstance(g, dict):
        assert "gpu_name" in g
        assert g["gpu_kind"] == "nvidia"


def test_apple_returns_none_or_dict() -> None:
    g = m._try_apple()
    assert g is None or isinstance(g, dict)
    if isinstance(g, dict):
        assert g["gpu_kind"] == "apple"
