from __future__ import annotations

from pathlib import Path

import httpx
from jw_core.vision.vlm import StructuredPage
from jw_core.vision.vlm_providers.qwen3vl_api import Qwen3VLAPIProvider


def _mock_transport(payload: str) -> httpx.MockTransport:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={"output": {"choices": [{"message": {"content": [{"text": payload}]}}]}},
        )

    return httpx.MockTransport(handler)


def test_unavailable_without_api_key(monkeypatch) -> None:
    monkeypatch.delenv("JW_QWEN3VL_API_KEY", raising=False)
    assert Qwen3VLAPIProvider().is_available() is False


def test_available_with_key(monkeypatch) -> None:
    monkeypatch.setenv("JW_QWEN3VL_API_KEY", "k")
    monkeypatch.setenv("JW_QWEN3VL_API_BASE", "https://dashscope.aliyuncs.com")
    p = Qwen3VLAPIProvider(client=httpx.Client(transport=_mock_transport("{}")))
    assert p.is_available()


def test_extract_structured(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("JW_QWEN3VL_API_KEY", "k")
    monkeypatch.setenv("JW_QWEN3VL_API_BASE", "https://dashscope.aliyuncs.com")
    img = tmp_path / "p.png"
    img.write_bytes(b"\x89PNG")
    payload = '{"blocks":[{"kind":"paragraph","text":"hola","lang_hint":"es"}],"language_detected":"es"}'
    p = Qwen3VLAPIProvider(client=httpx.Client(transport=_mock_transport(payload)))
    page = p.extract_structured(img, language="es")
    assert isinstance(page, StructuredPage)
    assert page.target == "api"
    assert page.provider_name == "qwen3vl_api"
    assert page.blocks[0].text == "hola"
