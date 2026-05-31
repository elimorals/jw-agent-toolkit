"""Offline unit tests for Veo3 adapter. Poll loop accelerated by stubbing time.sleep."""

from __future__ import annotations

import sys
import types
from pathlib import Path

import pytest
from jw_gen.models import GenerationRequest


def test_is_available_false_when_no_api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    from jw_gen.providers.video.veo3 import Veo3Provider

    assert Veo3Provider().is_available() is False


def test_is_available_false_when_sdk_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GEMINI_API_KEY", "fake-key")
    monkeypatch.setitem(sys.modules, "google.genai", None)
    from jw_gen.providers.video.veo3 import Veo3Provider

    assert Veo3Provider().is_available() is False


def test_cost_estimate_scales_with_duration(tmp_path: Path) -> None:
    from jw_gen.providers.video.veo3 import Veo3Provider

    p = Veo3Provider(work_dir=tmp_path)
    short = p.cost_estimate(GenerationRequest(prompt="x", kind="video", duration_s=4))
    long_ = p.cost_estimate(GenerationRequest(prompt="x", kind="video", duration_s=12))
    assert long_.usd > short.usd


def test_generate_polls_until_done_and_downloads(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    captured: dict = {}

    class _FakeVideo:
        pass

    class _FakeResponse:
        generated_videos = [types.SimpleNamespace(video=_FakeVideo())]

    class _FakeOp:
        def __init__(self) -> None:
            self.done = False
            self.response = _FakeResponse()
            self.calls = 0

    fake_op = _FakeOp()

    class _FakeModels:
        def generate_videos(self, *, model: str, prompt: str):
            captured["model"] = model
            captured["prompt"] = prompt
            return fake_op

    class _FakeOperations:
        def get(self, op):  # noqa: ARG002
            fake_op.calls += 1
            if fake_op.calls >= 2:
                fake_op.done = True
            return fake_op

    class _FakeFiles:
        def download(self, *, file, destination):  # noqa: ARG002
            captured["destination"] = destination
            Path(destination).write_bytes(b"\x00\x00\x00\x18ftypmp42FAKE")

    class _FakeClient:
        def __init__(self, api_key: str) -> None:
            captured["api_key"] = api_key
            self.models = _FakeModels()
            self.operations = _FakeOperations()
            self.files = _FakeFiles()

    fake_genai = types.SimpleNamespace(Client=_FakeClient)
    fake_google = types.ModuleType("google")
    fake_google.genai = fake_genai  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "google", fake_google)
    monkeypatch.setitem(sys.modules, "google.genai", fake_genai)
    monkeypatch.setenv("GEMINI_API_KEY", "fake-key")
    # Accelerate the poll loop.
    import time as _time

    monkeypatch.setattr(_time, "sleep", lambda _s: None)

    from jw_gen.providers.video.veo3 import Veo3Provider

    out = Veo3Provider(work_dir=tmp_path).generate(GenerationRequest(prompt="océano al amanecer", kind="video"))
    assert out.exists()
    assert out.read_bytes().startswith(b"\x00\x00\x00\x18ftypmp42")
    assert captured["model"] == "veo-3.0-generate-preview"
    assert fake_op.calls >= 1


def test_generate_raises_on_timeout(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    class _FakeOp:
        done = False
        response = None

    class _FakeModels:
        def generate_videos(self, *, model: str, prompt: str):  # noqa: ARG002
            return _FakeOp()

    class _FakeOperations:
        def get(self, op):  # noqa: ARG002
            return _FakeOp()

    class _FakeClient:
        def __init__(self, api_key: str) -> None:  # noqa: ARG002
            self.models = _FakeModels()
            self.operations = _FakeOperations()
            self.files = types.SimpleNamespace()

    fake_genai = types.SimpleNamespace(Client=_FakeClient)
    fake_google = types.ModuleType("google")
    fake_google.genai = fake_genai  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "google", fake_google)
    monkeypatch.setitem(sys.modules, "google.genai", fake_genai)
    monkeypatch.setenv("GEMINI_API_KEY", "fake-key")
    # Make time advance fast so we hit the deadline.
    import time as _time

    times = iter([0.0, 1000.0, 2000.0])
    monkeypatch.setattr(_time, "time", lambda: next(times))
    monkeypatch.setattr(_time, "sleep", lambda _s: None)

    from jw_gen.providers.video.veo3 import Veo3Provider

    with pytest.raises(RuntimeError, match="timed out"):
        Veo3Provider(work_dir=tmp_path).generate(GenerationRequest(prompt="x", kind="video"))
