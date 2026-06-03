"""NLLB-200 translation provider — Meta, 200 languages (CC-BY-NC-4.0).

Why a dedicated provider instead of a generic LLM call:

  - 200 languages with strong low-resource coverage. General LLMs hallucinate
    in low-resource languages (Yoruba, Twi, Kinyarwanda, Lingala) — NLLB is
    specifically trained on them with FLORES-200 supervision.
  - Encoder-decoder, deterministic. No prompt-engineering needed; identical
    output for identical input.
  - Runs locally via CTranslate2 INT8 → ~3.5 GB RAM for the 3.3B model on
    Mac M-series or any CUDA GPU. Zero data leaves the machine.

## Important license caveat

NLLB-200 ships under **CC-BY-NC-4.0** — non-commercial only. Acceptable for
individual / congregation use. **Blocks commercial deployment.** The provider
exposes `is_commercial_safe = False` so callers can route around it.

## Bootstrap

This provider does NOT need a separate venv (unlike Omnilingual): CTranslate2
publishes cp313 wheels. Install via the extra:

    uv add 'jw-core[translation-nllb]'

The first call downloads the model (~7 GB for 3.3B INT8). Override the model
id or directory:

    JW_NLLB_MODEL=OpenNMT/nllb-200-3.3B-ct2-int8
    JW_NLLB_MODEL_DIR=/path/to/local/ct2/dir
"""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Final

from jw_core.translation_providers import TranslationProvider

logger = logging.getLogger(__name__)

DEFAULT_MODEL: Final[str] = "OpenNMT/nllb-200-3.3B-ct2-int8"
DEFAULT_CACHE_DIR: Final[Path] = Path.home() / ".jw-core" / "nllb"

# ISO-639-1 → FLORES-200. Same convention NLLB tokenizer uses internally.
# Extend as new languages are exercised.
_ISO1_TO_FLORES: Final[dict[str, str]] = {
    "en": "eng_Latn", "es": "spa_Latn", "pt": "por_Latn", "fr": "fra_Latn",
    "de": "deu_Latn", "it": "ita_Latn", "ja": "jpn_Jpan", "ko": "kor_Hang",
    "zh": "zho_Hans", "ru": "rus_Cyrl", "ar": "arb_Arab", "tr": "tur_Latn",
    "nl": "nld_Latn", "pl": "pol_Latn", "cs": "ces_Latn", "hi": "hin_Deva",
    # Low-resource where NLLB shines vs general LLMs:
    "qu": "quy_Latn", "ay": "ayr_Latn", "gn": "grn_Latn",
    "rw": "kin_Latn", "sw": "swh_Latn", "ln": "lin_Latn",
    "yo": "yor_Latn", "ig": "ibo_Latn", "ha": "hau_Latn",
    "zu": "zul_Latn", "xh": "xho_Latn", "am": "amh_Ethi",
    "ti": "tir_Ethi", "so": "som_Latn", "uz": "uzn_Latn",
}


class NLLBTranslationError(RuntimeError):
    pass


class NLLBProvider(TranslationProvider):
    name = "nllb-200"
    is_commercial_safe = False  # CC-BY-NC-4.0

    def __init__(
        self,
        *,
        model_id: str | None = None,
        model_dir: Path | None = None,
        device: str = "auto",
        compute_type: str = "int8",
        beam_size: int = 4,
    ) -> None:
        self.model_id = model_id or os.getenv("JW_NLLB_MODEL", DEFAULT_MODEL)
        self.model_dir = Path(model_dir or os.getenv("JW_NLLB_MODEL_DIR") or DEFAULT_CACHE_DIR)
        self.device = device
        self.compute_type = compute_type
        self.beam_size = beam_size
        self._translator: object | None = None
        self._tokenizer: object | None = None

    # ── availability ────────────────────────────────────────────────

    def is_available(self) -> bool:
        try:
            import ctranslate2  # noqa: F401  # type: ignore[import-not-found]
            import transformers  # noqa: F401  # type: ignore[import-not-found]
        except ImportError:
            return False
        return True

    def supports_language_pair(self, source: str, target: str) -> bool:
        """NLLB supports any (src, tgt) within its 200 languages."""
        return (
            self._normalize_lang(source) in _ISO1_TO_FLORES.values() or "_" in source
        ) and (self._normalize_lang(target) in _ISO1_TO_FLORES.values() or "_" in target)

    # ── translation ─────────────────────────────────────────────────

    def translate(self, text: str, *, source: str, target: str) -> str:
        if not self.is_available():
            raise NLLBTranslationError(
                "NLLB deps missing. `uv add 'jw-core[translation-nllb]'` "
                "(or pip install ctranslate2 transformers sentencepiece)."
            )
        if not text.strip():
            return text

        src = self._normalize_lang(source)
        tgt = self._normalize_lang(target)
        tokenizer = self._get_tokenizer()
        translator = self._get_translator()

        tokenizer.src_lang = src  # type: ignore[attr-defined]
        tokens = tokenizer(text, return_tensors=None)["input_ids"]
        # `tokens` is a list[int]; CTranslate2 wants list[list[str]] of source pieces.
        source_pieces = tokenizer.convert_ids_to_tokens(tokens)  # type: ignore[attr-defined]

        target_prefix = [tgt]
        try:
            results = translator.translate_batch(  # type: ignore[attr-defined]
                [source_pieces],
                target_prefix=[target_prefix],
                beam_size=self.beam_size,
            )
        except Exception as exc:  # noqa: BLE001
            raise NLLBTranslationError(f"NLLB translation failed: {exc!r}") from exc

        out_pieces = results[0].hypotheses[0][1:]  # drop the target_prefix token
        out_ids = tokenizer.convert_tokens_to_ids(out_pieces)  # type: ignore[attr-defined]
        return tokenizer.decode(out_ids, skip_special_tokens=True)  # type: ignore[attr-defined]

    # ── internals ───────────────────────────────────────────────────

    def _normalize_lang(self, code: str) -> str:
        if "_" in code:
            return code  # already FLORES
        return _ISO1_TO_FLORES.get(code.lower(), code)

    def _get_translator(self) -> object:
        if self._translator is not None:
            return self._translator
        try:
            import ctranslate2  # type: ignore[import-not-found]
        except ImportError as e:  # pragma: no cover
            raise NLLBTranslationError("ctranslate2 import broken") from e

        model_path = self._resolve_model_dir()
        self._translator = ctranslate2.Translator(str(model_path), device=self.device, compute_type=self.compute_type)
        return self._translator

    def _get_tokenizer(self) -> object:
        if self._tokenizer is not None:
            return self._tokenizer
        try:
            from transformers import AutoTokenizer  # type: ignore[import-not-found]
        except ImportError as e:  # pragma: no cover
            raise NLLBTranslationError("transformers import broken") from e
        # NLLB uses SentencePiece; load the original facebook model's tokenizer
        # (the CT2 conversion strips it). 600M tokenizer matches all NLLB-200 sizes.
        self._tokenizer = AutoTokenizer.from_pretrained("facebook/nllb-200-distilled-600M")
        return self._tokenizer

    def _resolve_model_dir(self) -> Path:
        """Locate the CTranslate2 model directory; download from HF if needed."""
        if self.model_dir.is_dir() and any(self.model_dir.iterdir()):
            return self.model_dir
        try:
            from huggingface_hub import snapshot_download  # type: ignore[import-not-found]
        except ImportError as e:  # pragma: no cover
            raise NLLBTranslationError(
                "huggingface_hub missing. Install jw-core[translation-nllb] which includes it."
            ) from e
        self.model_dir.parent.mkdir(parents=True, exist_ok=True)
        logger.info("Downloading NLLB model %s to %s", self.model_id, self.model_dir)
        snapshot_download(repo_id=self.model_id, local_dir=str(self.model_dir))
        return self.model_dir
