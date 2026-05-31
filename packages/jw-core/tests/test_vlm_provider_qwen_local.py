"""Local Qwen3-VL: factory chooses backend by env / target.

We test the dispatch logic only — never load a real model. Each backend is
behind a `_BackendProtocol` so we can inject fakes.
"""

from __future__ import annotations

from pathlib import Path

from jw_core.vision.vlm import StructuredPage
from jw_core.vision.vlm_providers.qwen3vl_local import Qwen3VLProvider


class _FakeBackend:
    name = "fake-backend"

    def __init__(self, payload: str = "") -> None:
        self.payload = payload
        self.calls: list[Path | bytes] = []

    def available(self) -> bool:
        return True

    def generate(self, image: Path | bytes, prompt: str) -> str:  # noqa: ARG002
        self.calls.append(image)
        return self.payload or '{"blocks":[{"kind":"paragraph","text":"local-out","lang_hint":"en"}],"language_detected":"en"}'


def test_unavailable_when_no_backend() -> None:
    p = Qwen3VLProvider(backends=[])
    assert p.is_available() is False


def test_uses_first_available_backend(tmp_path: Path) -> None:
    img = tmp_path / "p.png"
    img.write_bytes(b"\x89PNG")
    backend = _FakeBackend()
    p = Qwen3VLProvider(target="mlx", backends=[backend])
    assert p.is_available()
    page = p.extract_structured(img, language="en")
    assert isinstance(page, StructuredPage)
    assert page.provider_name == "qwen3vl_local"
    assert page.target == "mlx"
    assert backend.calls == [img]
    assert page.blocks[0].text == "local-out"


def test_falls_back_to_paragraph_on_bad_json(tmp_path: Path) -> None:
    img = tmp_path / "p.png"
    img.write_bytes(b"\x89PNG")
    backend = _FakeBackend(payload="not json at all")
    p = Qwen3VLProvider(target="cpu", backends=[backend])
    page = p.extract_structured(img, language="en")
    assert len(page.blocks) == 1
    assert "not json" in page.raw_text_fallback


def test_skips_unavailable_backends(tmp_path: Path) -> None:
    img = tmp_path / "p.png"
    img.write_bytes(b"\x89PNG")

    class _Down:
        name = "down"

        def available(self) -> bool:
            return False

        def generate(self, image, prompt):  # noqa: ARG002
            raise AssertionError("should not be called")

    good = _FakeBackend()
    p = Qwen3VLProvider(target="cpu", backends=[_Down(), good])
    p.extract_structured(img, language="en")
    assert good.calls == [img]
