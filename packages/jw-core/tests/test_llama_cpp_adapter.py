"""Tests for LlamaCppAdapter — stub the llama_cpp module."""

from __future__ import annotations

import asyncio
import sys
import types

import pytest

from jw_core.grammar.schemas import AgentResultModel


def _install_fake_llama_cpp(monkeypatch: pytest.MonkeyPatch) -> list[dict]:
    captured: list[dict] = []

    class _LlamaGrammar:
        @staticmethod
        def from_string(s: str) -> object:
            captured.append({"grammar": s})
            return object()

    class _Llama:
        def __init__(self, **kwargs: object) -> None:
            captured.append({"init": kwargs})

        def __call__(self, prompt: str, **kwargs: object) -> dict[str, object]:
            captured.append({"prompt": prompt, **kwargs})
            return {
                "choices": [
                    {
                        "text": (
                            '{"query":"q","agent_name":"a","findings":'
                            '[{"summary":"ok",'
                            '"citation":{"url":"https://wol.jw.org/en/wol/d/r1/lp-e/2024",'
                            '"title":"","kind":"article"},'
                            '"excerpt":""}],"warnings":[]}'
                        )
                    }
                ]
            }

    fake = types.ModuleType("llama_cpp")
    fake.Llama = _Llama  # type: ignore[attr-defined]
    fake.LlamaGrammar = _LlamaGrammar  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "llama_cpp", fake)
    return captured


def test_llama_cpp_adapter_passes_grammar(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    captured = _install_fake_llama_cpp(monkeypatch)
    fake_model = tmp_path / "model.gguf"
    fake_model.write_bytes(b"\x00")  # presence check only
    from jw_core.privacy.llama_cpp_adapter import LlamaCppAdapter

    raw = asyncio.run(
        LlamaCppAdapter(model_path=str(fake_model)).generate("p", json_schema=AgentResultModel)
    )
    parsed = AgentResultModel.model_validate_json(raw)
    assert parsed.findings[0].citation.url.startswith("https://wol.jw.org/")
    assert any("grammar" in c for c in captured)


def test_llama_cpp_adapter_requires_model_path(monkeypatch: pytest.MonkeyPatch) -> None:
    _install_fake_llama_cpp(monkeypatch)
    from jw_core.privacy.llama_cpp_adapter import LlamaCppAdapter, LlamaCppError

    monkeypatch.delenv("JW_LLAMA_CPP_MODEL", raising=False)
    with pytest.raises(LlamaCppError):
        asyncio.run(LlamaCppAdapter().generate("p", json_schema=AgentResultModel))


def test_llama_cpp_adapter_is_available_when_module_importable(
    monkeypatch: pytest.MonkeyPatch, tmp_path
) -> None:
    _install_fake_llama_cpp(monkeypatch)
    fake_model = tmp_path / "m.gguf"
    fake_model.write_bytes(b"\x00")
    from jw_core.privacy.llama_cpp_adapter import LlamaCppAdapter

    assert asyncio.run(LlamaCppAdapter(model_path=str(fake_model)).is_available()) is True
