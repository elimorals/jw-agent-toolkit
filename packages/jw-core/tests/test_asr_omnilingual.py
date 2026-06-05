"""F52 — unit tests for the Omnilingual ASR provider (subprocess-based).

The provider drives an `omnilingual_worker.py` script inside a dedicated
Python 3.12 venv (because `fairseq2` has no cp313 wheels). Tests patch
`subprocess.run` so we don't need the venv, the model, or the audio file.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from unittest.mock import patch

import pytest
from jw_core.audio.asr_providers.omnilingual import (
    DEFAULT_MODEL_CARD,
    OmnilingualProvider,
)
from jw_core.audio.transcription import TranscriptionError


def _fake_venv(tmp_path: Path) -> Path:
    """Create a minimal `bin/python` so `is_file()` checks pass."""
    venv_dir = tmp_path / "venv"
    (venv_dir / "bin").mkdir(parents=True)
    (venv_dir / "bin" / "python").write_text("#!fake\n")
    (venv_dir / "bin" / "python").chmod(0o755)
    return venv_dir


def test_venv_python_path_resolution(tmp_path: Path) -> None:
    """`venv_python` finds the right binary under bin/."""
    venv = _fake_venv(tmp_path)
    p = OmnilingualProvider(venv_dir=venv)
    assert p.venv_python.parent.name == "bin"
    assert p.venv_python.is_file()


def test_is_available_false_without_venv(tmp_path: Path) -> None:
    """No venv → unavailable, no subprocess calls."""
    p = OmnilingualProvider(venv_dir=tmp_path / "nope")
    assert p.is_available() is False


def test_is_available_false_when_import_fails(tmp_path: Path) -> None:
    """Venv exists but omnilingual_asr import fails → unavailable."""
    venv = _fake_venv(tmp_path)
    p = OmnilingualProvider(venv_dir=venv)
    with patch("subprocess.run", return_value=subprocess.CompletedProcess([], returncode=1)):
        assert p.is_available() is False


def test_is_available_true_when_import_succeeds(tmp_path: Path) -> None:
    venv = _fake_venv(tmp_path)
    p = OmnilingualProvider(venv_dir=venv)
    with patch("subprocess.run", return_value=subprocess.CompletedProcess([], returncode=0)):
        assert p.is_available() is True


def test_transcribe_raises_when_venv_missing(tmp_path: Path) -> None:
    p = OmnilingualProvider(venv_dir=tmp_path / "nope")
    with pytest.raises(TranscriptionError, match="venv not found"):
        p.transcribe(Path("/tmp/x.wav"), language="en")


def test_transcribe_raises_when_omnilingual_not_installed(tmp_path: Path) -> None:
    venv = _fake_venv(tmp_path)
    p = OmnilingualProvider(venv_dir=venv)
    with patch("subprocess.run", return_value=subprocess.CompletedProcess([], returncode=1)):
        with pytest.raises(TranscriptionError, match="not installed inside it"):
            p.transcribe(Path("/tmp/x.wav"), language="en")


def test_transcribe_normalizes_iso1_to_flores(tmp_path: Path) -> None:
    """The worker must receive `spa_Latn`, not `es`."""
    venv = _fake_venv(tmp_path)
    p = OmnilingualProvider(venv_dir=venv)
    captured: dict[str, list[str]] = {}

    def fake_run(argv, **kwargs):
        captured["argv"] = argv
        if "-c" in argv:
            return subprocess.CompletedProcess(argv, returncode=0)  # is_available check
        return subprocess.CompletedProcess(
            argv,
            returncode=0,
            stdout=json.dumps({"text": "hola mundo", "language": "spa_Latn"}),
            stderr="",
        )

    with patch("subprocess.run", side_effect=fake_run):
        out = p.transcribe(Path("/tmp/x.wav"), language="es")

    assert out.text == "hola mundo"
    assert out.language == "spa_Latn"
    assert "--lang" in captured["argv"]
    assert "spa_Latn" in captured["argv"]
    assert "--model-card" in captured["argv"]
    assert DEFAULT_MODEL_CARD in captured["argv"]


def test_transcribe_passes_flores_through_unchanged(tmp_path: Path) -> None:
    venv = _fake_venv(tmp_path)
    p = OmnilingualProvider(venv_dir=venv)
    captured: dict[str, list[str]] = {}

    def fake_run(argv, **kwargs):
        captured["argv"] = argv
        if "-c" in argv:
            return subprocess.CompletedProcess(argv, returncode=0)
        return subprocess.CompletedProcess(argv, returncode=0, stdout='{"text":"","language":"que_Latn"}', stderr="")

    with patch("subprocess.run", side_effect=fake_run):
        p.transcribe(Path("/tmp/x.wav"), language="que_Latn")
    assert "que_Latn" in captured["argv"]


def test_transcribe_propagates_worker_exit_code(tmp_path: Path) -> None:
    venv = _fake_venv(tmp_path)
    p = OmnilingualProvider(venv_dir=venv)

    def fake_run(argv, **kwargs):
        if "-c" in argv:
            return subprocess.CompletedProcess(argv, returncode=0)
        return subprocess.CompletedProcess(argv, returncode=3, stdout="", stderr="pipeline failure: OOM")

    with patch("subprocess.run", side_effect=fake_run):
        with pytest.raises(TranscriptionError, match="exited 3.*OOM"):
            p.transcribe(Path("/tmp/x.wav"), language="en")


def test_transcribe_handles_invalid_json_from_worker(tmp_path: Path) -> None:
    venv = _fake_venv(tmp_path)
    p = OmnilingualProvider(venv_dir=venv)

    def fake_run(argv, **kwargs):
        if "-c" in argv:
            return subprocess.CompletedProcess(argv, returncode=0)
        return subprocess.CompletedProcess(argv, returncode=0, stdout="not json at all", stderr="")

    with patch("subprocess.run", side_effect=fake_run):
        with pytest.raises(TranscriptionError, match="invalid JSON"):
            p.transcribe(Path("/tmp/x.wav"), language="en")


def test_supports_language_consults_worker(tmp_path: Path) -> None:
    venv = _fake_venv(tmp_path)
    p = OmnilingualProvider(venv_dir=venv)

    def fake_run(argv, **kwargs):
        if "-c" in argv and "supported_langs" in argv[-1]:
            return subprocess.CompletedProcess(argv, returncode=0, stdout="yes\n", stderr="")
        return subprocess.CompletedProcess(argv, returncode=0)  # is_available

    with patch("subprocess.run", side_effect=fake_run):
        assert p.supports_language("eng_Latn") is True


def test_supports_language_false_when_unsupported(tmp_path: Path) -> None:
    venv = _fake_venv(tmp_path)
    p = OmnilingualProvider(venv_dir=venv)

    def fake_run(argv, **kwargs):
        if "-c" in argv and "supported_langs" in argv[-1]:
            return subprocess.CompletedProcess(argv, returncode=0, stdout="no\n", stderr="")
        return subprocess.CompletedProcess(argv, returncode=0)

    with patch("subprocess.run", side_effect=fake_run):
        assert p.supports_language("zzz_Zzzz") is False


def test_install_raises_when_python312_missing(tmp_path: Path) -> None:
    p = OmnilingualProvider(venv_dir=tmp_path / "venv")
    with patch("shutil.which", return_value=None):
        with pytest.raises(TranscriptionError, match="python3.12 not found"):
            p.install()


def test_model_card_env_override(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OMNILINGUAL_MODEL_CARD", "omniASR_LLM_Unlimited_7B_v2")
    venv = _fake_venv(tmp_path)
    p = OmnilingualProvider(venv_dir=venv)
    captured: dict[str, list[str]] = {}

    def fake_run(argv, **kwargs):
        captured["argv"] = argv
        if "-c" in argv:
            return subprocess.CompletedProcess(argv, returncode=0)
        return subprocess.CompletedProcess(argv, returncode=0, stdout='{"text":"","language":"eng_Latn"}', stderr="")

    with patch("subprocess.run", side_effect=fake_run):
        p.transcribe(Path("/tmp/x.wav"), language="en")
    assert "omniASR_LLM_Unlimited_7B_v2" in captured["argv"]


def test_explicit_constructor_kwarg_wins_over_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OMNILINGUAL_MODEL_CARD", "omniASR_LLM_Unlimited_7B_v2")
    venv = _fake_venv(tmp_path)
    p = OmnilingualProvider(model_card="omniASR_CTC_1B", venv_dir=venv)
    assert p.model_card == "omniASR_CTC_1B"


def test_venv_dir_env_override(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("JW_OMNILINGUAL_VENV", str(tmp_path / "custom-venv"))
    p = OmnilingualProvider()
    assert p.venv_dir == tmp_path / "custom-venv"
