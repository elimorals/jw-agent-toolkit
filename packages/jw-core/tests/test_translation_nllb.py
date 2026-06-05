"""F53 — unit tests for the NLLB translation provider.

We don't download the 7 GB model in tests. Instead we patch CTranslate2's
`Translator` and the HF `AutoTokenizer` so the provider can be exercised
without weights. The end-to-end `translate_preserving_references` wrapper
is tested with a stub provider that round-trips text — that proves the
mask/restore flow without depending on NLLB itself.
"""

from __future__ import annotations

import sys
import types
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from jw_core.translation import translate_preserving_references
from jw_core.translation_providers import TranslationProvider
from jw_core.translation_providers.nllb import (
    DEFAULT_MODEL,
    NLLBProvider,
    NLLBTranslationError,
)


def test_is_available_false_when_deps_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setitem(sys.modules, "ctranslate2", None)
    monkeypatch.setitem(sys.modules, "transformers", None)
    p = NLLBProvider()
    assert p.is_available() is False


def test_translate_raises_without_deps(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setitem(sys.modules, "ctranslate2", None)
    monkeypatch.setitem(sys.modules, "transformers", None)
    p = NLLBProvider()
    with pytest.raises(NLLBTranslationError, match="deps missing"):
        p.translate("hello", source="en", target="es")


def test_empty_input_short_circuits(monkeypatch: pytest.MonkeyPatch) -> None:
    """Empty / whitespace input must not load the model."""
    _install_ct2_stub(monkeypatch, expect_called=False)
    p = NLLBProvider()
    assert p.translate("", source="en", target="es") == ""
    assert p.translate("   ", source="en", target="es") == "   "


def test_translate_routes_through_ctranslate2(monkeypatch: pytest.MonkeyPatch) -> None:
    """The provider must hand source pieces + target_prefix to CT2 correctly."""
    captured = _install_ct2_stub(monkeypatch, hypothesis=["spa_Latn", "▁hola", "▁mundo"])
    p = NLLBProvider()
    out = p.translate("hello world", source="en", target="es")
    assert out == "hola mundo"
    assert captured["src_lang"] == "eng_Latn"
    assert captured["target_prefix"] == [["spa_Latn"]]
    assert captured["source"] == [["▁hello", "▁world"]]


def test_flores_codes_passthrough(monkeypatch: pytest.MonkeyPatch) -> None:
    """If caller already supplies `kin_Latn`, no remapping happens."""
    captured = _install_ct2_stub(monkeypatch, hypothesis=["kin_Latn", "▁mwiriwe"])
    p = NLLBProvider()
    p.translate("hello", source="eng_Latn", target="kin_Latn")
    assert captured["src_lang"] == "eng_Latn"
    assert captured["target_prefix"] == [["kin_Latn"]]


def test_is_commercial_safe_flag() -> None:
    """NLLB is CC-BY-NC; this flag must be False so router can avoid it."""
    p = NLLBProvider()
    assert p.is_commercial_safe is False


def test_supports_language_pair() -> None:
    p = NLLBProvider()
    assert p.supports_language_pair("en", "es") is True
    assert p.supports_language_pair("en", "kin_Latn") is True
    assert p.supports_language_pair("klingon", "en") is False


def test_translate_propagates_ct2_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    _install_ct2_stub(monkeypatch, raise_on_translate=RuntimeError("CUDA OOM"))
    p = NLLBProvider()
    with pytest.raises(NLLBTranslationError, match="NLLB translation failed.*CUDA OOM"):
        p.translate("hello", source="en", target="es")


def test_model_id_env_override(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("JW_NLLB_MODEL", "OpenNMT/nllb-200-1.3B-ct2-int8")
    p = NLLBProvider()
    assert p.model_id == "OpenNMT/nllb-200-1.3B-ct2-int8"
    assert p.model_id != DEFAULT_MODEL


def test_translate_preserving_references_with_stub_provider() -> None:
    """The wrapper must mask → translate → restore. Stub provider echoes."""

    class _Echo(TranslationProvider):
        name = "echo"

        def is_available(self) -> bool:
            return True

        def supports_language_pair(self, source: str, target: str) -> bool:
            return True

        def translate(self, text: str, *, source: str, target: str) -> str:
            # Echo as-is: the masking is the part being tested here.
            return text

    src = "Como dice Juan 3:16, Dios amó al mundo."
    out = translate_preserving_references(src, source="es", target="en", provider=_Echo())
    # The reference is rendered in English book naming after restore.
    assert "John 3:16" in out
    # The body around it survives untouched (since echo).
    assert "Como dice" in out and "Dios amó al mundo" in out


# ── stubs ───────────────────────────────────────────────────────────────


def _install_ct2_stub(
    monkeypatch: pytest.MonkeyPatch,
    *,
    hypothesis: list[str] | None = None,
    expect_called: bool = True,
    raise_on_translate: Exception | None = None,
) -> dict[str, object]:
    """Build fake `ctranslate2` + `transformers` modules in sys.modules.

    Returns a `captured` dict the test reads back to assert call shapes.
    """
    captured: dict[str, object] = {}

    class _FakeTokenizer:
        def __init__(self) -> None:
            self.src_lang = ""

        def __call__(self, text: str, **kwargs: object) -> dict[str, list[int]]:
            captured["src_lang"] = self.src_lang
            return {"input_ids": [1, 2, 3]}

        def convert_ids_to_tokens(self, ids: list[int]) -> list[str]:
            return ["▁hello", "▁world"]

        def convert_tokens_to_ids(self, tokens: list[str]) -> list[int]:
            return list(range(len(tokens)))

        def decode(self, ids: list[int], skip_special_tokens: bool = True) -> str:
            # The hypothesis[1:] (without target_prefix) tells us the result.
            hyp = hypothesis or ["spa_Latn", "▁hola", "▁mundo"]
            words = [t.lstrip("▁") for t in hyp[1:]]
            return " ".join(words)

    class _FakeTranslator:
        def __init__(self, path: str, **kwargs: object) -> None:
            captured["model_path"] = path
            captured["device"] = kwargs.get("device")
            captured["compute_type"] = kwargs.get("compute_type")

        def translate_batch(self, source, *, target_prefix, beam_size):  # type: ignore[no-untyped-def]
            if raise_on_translate:
                raise raise_on_translate
            if not expect_called:
                pytest.fail("translate_batch should not have been called")
            captured["source"] = source
            captured["target_prefix"] = target_prefix
            captured["beam_size"] = beam_size
            result = MagicMock()
            result.hypotheses = [hypothesis or ["spa_Latn", "▁hola", "▁mundo"]]
            return [result]

    ct2 = types.ModuleType("ctranslate2")
    ct2.Translator = _FakeTranslator  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "ctranslate2", ct2)

    tx = types.ModuleType("transformers")

    class _AutoTokenizer:
        @classmethod
        def from_pretrained(cls, *args: object, **kwargs: object) -> _FakeTokenizer:
            return _FakeTokenizer()

    tx.AutoTokenizer = _AutoTokenizer  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "transformers", tx)

    # Stub model dir so _resolve_model_dir doesn't try huggingface_hub.
    from jw_core.translation_providers import nllb as nllb_mod

    monkeypatch.setattr(
        NLLBProvider,
        "_resolve_model_dir",
        lambda self: Path("/fake/model"),
        raising=True,
    )
    _ = nllb_mod  # silence unused import in case linters move it
    return captured
