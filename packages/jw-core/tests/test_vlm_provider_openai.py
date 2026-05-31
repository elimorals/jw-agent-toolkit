from __future__ import annotations

from pathlib import Path

from jw_core.vision.vlm import StructuredPage
from jw_core.vision.vlm_providers.openai_vision import OpenAIVisionProvider


class _FakeChat:
    def __init__(self, payload: str) -> None:
        self._payload = payload
        self.last_request: dict | None = None

    def create(self, **kwargs):
        self.last_request = kwargs

        class _Msg:
            def __init__(self, c: str) -> None:
                self.content = c

        class _Choice:
            def __init__(self, c: str) -> None:
                self.message = _Msg(c)

        class _Resp:
            def __init__(self, c: str) -> None:
                self.choices = [_Choice(c)]

        return _Resp(self._payload)


class _FakeClient:
    def __init__(self, payload: str) -> None:
        self.chat = type("X", (), {"completions": _FakeChat(payload)})()


def test_unavailable_without_api_key(monkeypatch) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    assert OpenAIVisionProvider().is_available() is False


def test_extract_structured(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    img = tmp_path / "p.png"
    img.write_bytes(b"\x89PNG\r\n\x1a\nfake")
    payload = '{"blocks":[{"kind":"paragraph","text":"hello","lang_hint":"en"}],"language_detected":"en"}'
    client = _FakeClient(payload)
    p = OpenAIVisionProvider(client=client, model="gpt-4o-mini")
    page = p.extract_structured(img, language="en")
    assert isinstance(page, StructuredPage)
    assert page.provider_name == "openai_vision"
    assert page.target == "api"
    assert page.blocks[0].text == "hello"
    req = client.chat.completions.last_request
    assert req["model"] == "gpt-4o-mini"
    parts = req["messages"][0]["content"]
    assert any(p["type"] == "image_url" for p in parts)


def test_model_can_be_overridden_via_env(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "sk")
    monkeypatch.setenv("JW_OPENAI_VISION_MODEL", "gpt-5")
    img = tmp_path / "p.png"
    img.write_bytes(b"\x89PNG")
    client = _FakeClient('{"blocks":[],"language_detected":"en"}')
    OpenAIVisionProvider(client=client).extract_structured(img, language="en")
    assert client.chat.completions.last_request["model"] == "gpt-5"
