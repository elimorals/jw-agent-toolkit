"""ClaudeVisionProvider: adapter on top of the anthropic SDK.

The model is *not* a new entity. It uses claude-haiku-4-5 / sonnet-4-6 /
opus-4-7, which are natively multimodal. We test by injecting a fake `client`.
"""

from __future__ import annotations

from pathlib import Path

from jw_core.vision.vlm import StructuredPage
from jw_core.vision.vlm_providers.claude_vision import ClaudeVisionProvider


class _FakeClient:
    def __init__(self, payload: str) -> None:
        self._payload = payload
        self.last_request: dict | None = None
        self.messages = self

    def create(self, **kwargs) -> object:
        self.last_request = kwargs

        class _Block:
            def __init__(self, text: str) -> None:
                self.text = text
                self.type = "text"

        class _Resp:
            def __init__(self, text: str) -> None:
                self.content = [_Block(text)]

        return _Resp(self._payload)


def test_provider_is_unavailable_without_api_key(monkeypatch) -> None:
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    p = ClaudeVisionProvider()
    assert p.is_available() is False


def test_provider_is_available_with_api_key_and_client(monkeypatch) -> None:
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test")
    p = ClaudeVisionProvider(client=_FakeClient("{}"))
    assert p.is_available() is True
    assert p.target == "api"


def test_extract_structured_parses_blocks(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test")
    img = tmp_path / "p.png"
    img.write_bytes(b"\x89PNG\r\n\x1a\nfake-bytes")
    payload = (
        '{"blocks":[{"kind":"header","text":"Juan 3","lang_hint":"es"},'
        '{"kind":"bible_ref","text":"Juan 3:16","lang_hint":"es"}],'
        '"language_detected":"es"}'
    )
    client = _FakeClient(payload)
    p = ClaudeVisionProvider(client=client, model="claude-haiku-4-5")
    page = p.extract_structured(img, language="es")
    assert isinstance(page, StructuredPage)
    assert page.provider_name == "claude_vision"
    assert page.target == "api"
    assert len(page.blocks) == 2
    assert client.last_request is not None
    assert client.last_request["model"] == "claude-haiku-4-5"
    content = client.last_request["messages"][0]["content"]
    kinds = [item["type"] for item in content]
    assert "image" in kinds and "text" in kinds


def test_extract_falls_back_to_paragraph_on_bad_json(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test")
    img = tmp_path / "p.png"
    img.write_bytes(b"\x89PNG")
    p = ClaudeVisionProvider(client=_FakeClient("not json"))
    page = p.extract_structured(img, language="en")
    assert len(page.blocks) == 1
    assert page.blocks[0].kind == "paragraph"
    assert "not json" in page.raw_text_fallback


def test_model_can_be_overridden_via_env(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test")
    monkeypatch.setenv("JW_CLAUDE_VISION_MODEL", "claude-sonnet-4-6")
    img = tmp_path / "p.png"
    img.write_bytes(b"\x89PNG")
    client = _FakeClient('{"blocks":[],"language_detected":"en"}')
    p = ClaudeVisionProvider(client=client)
    p.extract_structured(img, language="en")
    assert client.last_request is not None
    assert client.last_request["model"] == "claude-sonnet-4-6"
