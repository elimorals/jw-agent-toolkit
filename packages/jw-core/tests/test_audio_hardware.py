from __future__ import annotations

from unittest.mock import patch

from jw_core.audio import hardware


def test_detect_target_returns_nvidia_when_smi_present() -> None:
    with patch("shutil.which", return_value="/usr/bin/nvidia-smi"):
        assert hardware.detect_target() == "nvidia"


def test_detect_target_returns_mlx_on_apple_silicon() -> None:
    with (
        patch("shutil.which", return_value=None),
        patch("sys.platform", "darwin"),
        patch("platform.machine", return_value="arm64"),
    ):
        assert hardware.detect_target() == "mlx"


def test_detect_target_returns_cpu_fallback() -> None:
    with (
        patch("shutil.which", return_value=None),
        patch("sys.platform", "linux"),
        patch("platform.machine", return_value="x86_64"),
    ):
        assert hardware.detect_target() == "cpu"


def test_recommend_model_size_picks_turbo_with_vram() -> None:
    with patch.object(hardware, "available_vram_gb", return_value=12.0):
        assert hardware.recommend_model_size() == "large-v3-turbo"


def test_recommend_model_size_falls_back_to_base() -> None:
    with patch.object(hardware, "available_vram_gb", return_value=2.0):
        assert hardware.recommend_model_size() == "base"


def test_available_vram_gb_returns_float() -> None:
    val = hardware.available_vram_gb()
    assert isinstance(val, float)
    assert val >= 0.0
