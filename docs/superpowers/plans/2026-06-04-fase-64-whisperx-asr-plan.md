# Fase 64 — `whisperX` ASR provider con diarización Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: `superpowers:subagent-driven-development` (recommended) or `superpowers:executing-plans`. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Añadir un `ASRProvider` nuevo basado en `m-bain/whisperX` al stack de `jw_core.audio.asr_providers` para entregar (a) **diarización** (identificación de orador) y (b) **word-level timestamps** sobre transcripciones de discursos, asambleas, programas de aniversario y reuniones congregacionales. Estos dos features no los entrega `faster-whisper` solo y son la única razón por la que `whisperX` aporta valor real sobre lo ya integrado en F53 (omnilingual-asr) y stack `whisper-turbo` existente.

**Architecture:** Subclase `ASRProvider` siguiendo el patrón ya validado por `whisper_turbo.py` y `omnilingual.py`. Lazy import de `whisperx` para que la dep pesada (~3 GB con modelos) sea opt-in via extra `[asr-whisperx]`. Soporta dos modos: (1) **solo transcribe** sin diarización (más rápido), (2) **transcribe+diarize** con `pyannote.audio` (requiere HuggingFace token para descargar el modelo de diarización, pero el modelo se cachea y luego corre 100% local). Mapeo opcional segmento → `BibleRef` cuando el segmento es una lectura bíblica reconocible vía `parse_reference()`.

**Tech Stack:** Python 3.13 · `whisperx >= 3.4` (opt-in) · `pyannote.audio` (transitive, opt-in) · resto del stack `jw_core.audio` ya existente.

**Spec/origen brainstorm:** [`docs/conceptos/integraciones-priorizadas.md`](../../conceptos/integraciones-priorizadas.md) §"Re-evaluación honesta" punto 5. Valor real: transcribir discurso de asamblea de 60min con 3 oradores → mapear cada segmento al orador y al pasaje bíblico citado para ingest al RAG con metadata rica.

**Depende de:** F53 (precedente patrón polyglot Python para ASR pesadas), F34 (audio stack en general). NO depende de F58 ni F62.

---

## File map

Crea:
- `packages/jw-core/src/jw_core/audio/asr_providers/whisperx.py` — subclase `ASRProvider`.
- `packages/jw-core/tests/test_audio_asr_whisperx.py` — tests con fakes + opt-in real.
- `packages/jw-core/tests/fixtures/audio/discurso_mini.wav` — audio sintético de 5s generado por script.
- `packages/jw-core/tests/fixtures/audio/build_audio_fixtures.py` — script reproducible.
- `docs/guias/asr-diarizacion.md` — guía operativa.

Modifica:
- `packages/jw-core/pyproject.toml` — añadir `asr-whisperx = ["whisperx>=3.4"]`.
- `packages/jw-core/src/jw_core/audio/transcription.py` — registrar `WhisperXProvider` en `_all_providers()` y opcionalmente prepender a `DEFAULT_ASR_CHAIN` (decisión: NO prepender por default, solo activa via env `JW_ASR_PROVIDER=whisperx` — porque carga 3 GB).
- `packages/jw-core/src/jw_core/audio/__init__.py` — exportar dataclass `DiarizedSegment`.
- `packages/jw-cli/src/jw_cli/...` — añadir opción `--diarize` al comando `jw audio transcribe` (si existe; si no, este task lo crea).
- `packages/jw-mcp/src/jw_mcp/server.py` — añadir tool `transcribe_audio_diarized`.
- `docs/ROADMAP.md`, `docs/README.md`, master plan — updates.

---

## Decisiones clave de diseño (anti-placeholder)

### Por qué NO incluir whisperX en `DEFAULT_ASR_CHAIN`
La cadena default es `["deepgram", "whisper-turbo", "omnilingual"]`. Añadir whisperX por default obliga descargar el modelo y dependencias diarización aunque el usuario nunca las use. Decisión: whisperX se selecciona explícitamente (`JW_ASR_PROVIDER=whisperx` o param `name="whisperx"`). El precedente F53 con `omnilingual` (que sí está en la chain) es distinto porque su valor único — 1672 idiomas — justifica el coste.

### Diarización condicional al param `diarize=True`
`transcribe()` del Protocol no acepta `diarize` (firma fija). Decisión: añadir `transcribe_diarized()` como **método extra** al provider, no al Protocol. El router NO conoce diarización — el usuario que la quiere llama directo al provider:
```python
provider = get_asr_provider(name="whisperx")
result = provider.transcribe_diarized(audio_path, language="es")
```
Esto mantiene el Protocol estable y entrega la feature como API explícita.

### Mapeo segmento → BibleRef opcional, en post-processing
Si un segmento dice *"Génesis 1:1 dice..."*, queremos extraer `BibleRef(book_num=1, chapter=1, verse_start=1)`. F64 lo hace en una capa post-process **opcional** (`enrich_with_bible_refs=True`) que usa `parse_reference()` de `jw_core.parsers.reference`. Sin esto, los segmentos solo tienen texto + speaker + timestamps. Con esto, `metadata.bible_refs: list[BibleRef]` por segmento.

### Tokens HF para diarización: gestionar el botón rojo
`pyannote/speaker-diarization-3.1` requiere aceptar términos en HuggingFace + token. F64:
1. Lee `HF_TOKEN` o `HUGGING_FACE_HUB_TOKEN` env vars.
2. Si no hay token y `diarize=True`, lanza `WhisperXDiarizationError("Diarization requires HF token...")` con mensaje claro.
3. Documenta el setup en la guía.
**NO descarga ni guarda el token en disco**. NO trata de hacer login automático.

### Salida unificada — extender `TranscriptionResult` opcionalmente
La diarización añade información: `speaker_id` por segmento. Decisión: **NO modificar** `TranscriptionResult` (es API estable consumida por F53). En lugar de eso, devolver una nueva clase `DiarizedResult` que es superset:
```python
@dataclass
class DiarizedSegment(TranscriptionSegment):
    speaker_id: str | None = None
    bible_refs: tuple[BibleRef, ...] = ()

@dataclass
class DiarizedResult(TranscriptionResult):
    segments: list[DiarizedSegment]
    speaker_count: int
```
Si el usuario llama `transcribe()` simple sobre whisperX provider, devuelve `TranscriptionResult` legacy (compatibilidad). Si llama `transcribe_diarized()`, devuelve `DiarizedResult`.

### Fixture audio sintético reproducible
Usar `gTTS` (Google TTS) en un script para generar 5s de audio "Génesis uno uno" en español + "John three sixteen" en inglés. ~50 KB cada uno. **Sin** copyright (texto literal de ref bíblica + TTS sintético). Generado en CI con `--with gtts`.

---

### Task 1: Extras + fixture audio

**Files:**
- Modify: `packages/jw-core/pyproject.toml`
- Create: `packages/jw-core/tests/fixtures/audio/build_audio_fixtures.py`
- Create: `packages/jw-core/tests/fixtures/audio/discurso_mini.wav` (generado)

- [ ] **Step 1: Añadir extra**

En `packages/jw-core/pyproject.toml`, dentro de `[project.optional-dependencies]`:
```toml
asr-whisperx = ["whisperx>=3.4.0"]
```

Y actualizar `asr-premium` si ya agrupa:
```toml
asr-premium = ["jw-core[asr-turbo,asr-deepgram,asr-whisperx]"]
```

- [ ] **Step 2: Script de fixture audio**

```python
# packages/jw-core/tests/fixtures/audio/build_audio_fixtures.py
"""Genera fixtures audio sintéticos para tests de ASR providers.

Crea:
- discurso_mini.wav (~5s, contiene texto con una ref bíblica en español)
- discurso_en.wav (~5s, texto con ref bíblica en inglés)

Las refs bíblicas son texto público (citas), TTS sintético = sin copyright.
"""
from __future__ import annotations

import io
from pathlib import Path

from gtts import gTTS

HERE = Path(__file__).parent

SCRIPTS = {
    "discurso_mini.wav": ("es", "Bienvenidos hermanos. Leamos juntos Génesis uno uno."),
    "discurso_en.wav": ("en", "Brothers, today we read John three sixteen together."),
}


def synth_to_wav(text: str, lang: str, output: Path) -> None:
    tts = gTTS(text=text, lang=lang)
    mp3_buf = io.BytesIO()
    tts.write_to_fp(mp3_buf)
    mp3_buf.seek(0)

    # Convert MP3 to WAV usando ffmpeg (subprocess)
    import subprocess

    mp3_path = output.with_suffix(".mp3")
    mp3_path.write_bytes(mp3_buf.read())
    subprocess.check_call(
        [
            "ffmpeg",
            "-y",
            "-i", str(mp3_path),
            "-ar", "16000",
            "-ac", "1",
            str(output),
        ],
        stderr=subprocess.DEVNULL,
    )
    mp3_path.unlink()


def main() -> None:
    for filename, (lang, text) in SCRIPTS.items():
        out = HERE / filename
        synth_to_wav(text, lang, out)
        print(f"Wrote {out} ({out.stat().st_size} bytes)")


if __name__ == "__main__":
    main()
```

- [ ] **Step 3: Generar fixtures**

```bash
cd /Users/elias/Documents/Trabajo/jw-agent-toolkit
uv run --with gtts python packages/jw-core/tests/fixtures/audio/build_audio_fixtures.py
```
Expected: `Wrote .../discurso_mini.wav (NNNN bytes)` y `Wrote .../discurso_en.wav (NNNN bytes)`.

> **Requisito**: `ffmpeg` debe estar instalado en el sistema. Si no, instalar (`brew install ffmpeg` en macOS).

- [ ] **Step 4: Commit**

```bash
git add packages/jw-core/pyproject.toml packages/jw-core/tests/fixtures/audio/
git commit -m "feat(jw-core): F64.1 audio fixtures plus asr-whisperx extra"
```

---

### Task 2: `DiarizedSegment` y `DiarizedResult` dataclasses

**Files:**
- Modify: `packages/jw-core/src/jw_core/audio/transcription.py` (o donde viva `TranscriptionResult`)
- Create: `packages/jw-core/tests/test_audio_diarized_models.py`

- [ ] **Step 1: Failing test**

```python
# packages/jw-core/tests/test_audio_diarized_models.py
"""F64 — modelos para diarización extienden TranscriptionResult sin breaking."""
from jw_core.audio.transcription import (
    DiarizedResult,
    DiarizedSegment,
    TranscriptionResult,
    TranscriptionSegment,
)


def test_diarized_segment_is_subclass_of_transcription_segment():
    assert issubclass(DiarizedSegment, TranscriptionSegment)


def test_diarized_segment_has_speaker_id():
    seg = DiarizedSegment(start=0.0, end=1.5, text="Hola hermanos", speaker_id="SPEAKER_00")
    assert seg.speaker_id == "SPEAKER_00"
    assert seg.text == "Hola hermanos"


def test_diarized_segment_bible_refs_defaults_empty():
    seg = DiarizedSegment(start=0.0, end=1.5, text="hola")
    assert seg.bible_refs == ()


def test_diarized_result_extends_transcription_result():
    result = DiarizedResult(
        text="Hola hermanos. Génesis 1:1.",
        language="es",
        duration=3.0,
        segments=[
            DiarizedSegment(start=0.0, end=1.5, text="Hola hermanos.", speaker_id="SPEAKER_00"),
            DiarizedSegment(start=1.5, end=3.0, text="Génesis 1:1.", speaker_id="SPEAKER_00"),
        ],
        speaker_count=1,
    )
    assert isinstance(result, TranscriptionResult)
    assert result.speaker_count == 1
```

- [ ] **Step 2: Run, expect FAIL**

Run: `uv run pytest packages/jw-core/tests/test_audio_diarized_models.py -v`
Expected: ImportError.

- [ ] **Step 3: Implementar dataclasses**

En `packages/jw-core/src/jw_core/audio/transcription.py`, añadir al final del archivo (o al lado de `TranscriptionResult`):

```python
from dataclasses import dataclass, field

from jw_core.models import BibleRef


@dataclass
class DiarizedSegment(TranscriptionSegment):
    """Segmento con identificación de orador y refs bíblicas opcionales."""
    speaker_id: str | None = None
    bible_refs: tuple[BibleRef, ...] = field(default_factory=tuple)


@dataclass
class DiarizedResult(TranscriptionResult):
    """Result de transcripción con diarización. Subclase backwards-compatible:
    código que espera TranscriptionResult sigue funcionando."""
    segments: list[DiarizedSegment] = field(default_factory=list)  # type: ignore[assignment]
    speaker_count: int = 0
```

> **Nota**: `field(default_factory=...)` requerido porque `TranscriptionSegment`/`TranscriptionResult` ya tienen sus propios defaults. Verifica que `TranscriptionSegment` es `@dataclass` (no Pydantic) consultando el archivo. Si es Pydantic, adapta a `BaseModel` subclass con `model_config = ConfigDict(extra="forbid")`.

- [ ] **Step 4: Run, expect PASS**

Run: `uv run pytest packages/jw-core/tests/test_audio_diarized_models.py -v`
Expected: 4 passed.

- [ ] **Step 5: Commit**

```bash
git add packages/jw-core/src/jw_core/audio/transcription.py packages/jw-core/tests/test_audio_diarized_models.py
git commit -m "feat(jw-core): F64.2 add DiarizedSegment DiarizedResult dataclasses"
```

---

### Task 3: `WhisperXProvider` con `is_available()` lazy

**Files:**
- Create: `packages/jw-core/src/jw_core/audio/asr_providers/whisperx.py`
- Create: `packages/jw-core/tests/test_audio_asr_whisperx.py`

- [ ] **Step 1: Failing test para `is_available()`**

```python
# packages/jw-core/tests/test_audio_asr_whisperx.py
"""F64 — WhisperXProvider con diarización opt-in."""
from __future__ import annotations

from pathlib import Path

import pytest

FIXTURE_ES = Path(__file__).parent / "fixtures" / "audio" / "discurso_mini.wav"
FIXTURE_EN = Path(__file__).parent / "fixtures" / "audio" / "discurso_en.wav"


def test_provider_metadata():
    from jw_core.audio.asr_providers.whisperx import WhisperXProvider

    p = WhisperXProvider()
    assert p.name == "whisperx"
    assert p.target in {"cuda", "cpu"}
    assert "es" in p.languages_supported
    assert "en" in p.languages_supported


def test_is_available_returns_false_without_dep():
    """Sin whisperx instalado, is_available debe ser False (no raise)."""
    from jw_core.audio.asr_providers.whisperx import WhisperXProvider

    p = WhisperXProvider()
    available = p.is_available()
    assert isinstance(available, bool)
    # Si la dep está, es True; si no, False. No assertion hard.


@pytest.mark.skipif(
    not __import__("importlib").util.find_spec("whisperx"),
    reason="whisperx not installed",
)
def test_transcribe_returns_transcription_result_legacy():
    """Llamada sin diarización: devuelve TranscriptionResult compatible."""
    from jw_core.audio.asr_providers.whisperx import WhisperXProvider
    from jw_core.audio.transcription import TranscriptionResult

    p = WhisperXProvider(model_size="tiny")  # rápido para test
    result = p.transcribe(FIXTURE_ES, language="es")
    assert isinstance(result, TranscriptionResult)
    assert result.language == "es"
    assert len(result.text) > 0


@pytest.mark.skipif(
    not __import__("importlib").util.find_spec("whisperx"),
    reason="whisperx not installed",
)
def test_transcribe_diarized_marks_speakers():
    """transcribe_diarized devuelve DiarizedResult con speaker_id."""
    from jw_core.audio.asr_providers.whisperx import WhisperXProvider
    from jw_core.audio.transcription import DiarizedResult
    import os

    if not os.environ.get("HF_TOKEN"):
        pytest.skip("HF_TOKEN not set; diarization needs pyannote model access")

    p = WhisperXProvider(model_size="tiny")
    result = p.transcribe_diarized(FIXTURE_ES, language="es")
    assert isinstance(result, DiarizedResult)
    # Audio de 1 orador → speaker_count >= 1
    assert result.speaker_count >= 1
    assert all(seg.speaker_id is not None for seg in result.segments)


@pytest.mark.skipif(
    not __import__("importlib").util.find_spec("whisperx"),
    reason="whisperx not installed",
)
def test_transcribe_diarized_enriches_bible_refs():
    """Con enrich_with_bible_refs=True, segmentos con menciones bíblicas
    obtienen `bible_refs`."""
    from jw_core.audio.asr_providers.whisperx import WhisperXProvider
    import os

    if not os.environ.get("HF_TOKEN"):
        pytest.skip("HF_TOKEN not set")

    p = WhisperXProvider(model_size="tiny")
    result = p.transcribe_diarized(
        FIXTURE_ES, language="es", enrich_with_bible_refs=True
    )
    has_ref = any(seg.bible_refs for seg in result.segments)
    # Audio dice "Génesis uno uno" → al menos 1 ref detectada
    assert has_ref
```

- [ ] **Step 2: Implementar provider**

```python
# packages/jw-core/src/jw_core/audio/asr_providers/whisperx.py
"""WhisperX provider: word-level timestamps + speaker diarization.

Carga la dep pesada (`whisperx`, ~3 GB con modelos) solo cuando se
instancia un job real, no en module import.

Modelo de diarización (`pyannote/speaker-diarization-3.1`) requiere:
1. Token HF accesible via env `HF_TOKEN` o `HUGGING_FACE_HUB_TOKEN`.
2. Aceptación de términos de uso en HuggingFace UI (una vez por cuenta).
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import ClassVar, Literal

from jw_core.audio.asr_providers import ASRProvider
from jw_core.audio.transcription import (
    DiarizedResult,
    DiarizedSegment,
    TranscriptionResult,
    TranscriptionSegment,
)


class WhisperXDiarizationError(RuntimeError):
    """Diarización pidió un token HF que no está disponible."""


def _detect_target() -> Literal["cuda", "cpu"]:
    try:
        import torch

        return "cuda" if torch.cuda.is_available() else "cpu"
    except ImportError:
        return "cpu"


class WhisperXProvider(ASRProvider):
    """ASR provider con diarización + word-level timestamps."""

    name = "whisperx"
    target: ClassVar[Literal["api", "nvidia", "mlx", "cpu", "cuda"]] = "cpu"
    languages_supported = {
        "en", "es", "pt", "fr", "de", "it", "ru", "zh", "ja", "ko",
        "nl", "tr", "pl", "uk", "cs", "ar", "hi", "vi", "th",
    }

    def __init__(self, model_size: str = "large-v3"):
        self.model_size = model_size
        self.target = _detect_target()  # type: ignore[assignment]
        self._asr_model = None
        self._align_model = None
        self._diarize_model = None

    def is_available(self) -> bool:
        try:
            import whisperx  # noqa: F401

            return True
        except ImportError:
            return False

    def transcribe(
        self,
        audio_path: Path,
        *,
        language: str | None = None,
        model_size: str = "auto",
    ) -> TranscriptionResult:
        """Transcripción rápida sin diarización (compatible con Protocol)."""
        return self._transcribe_impl(
            audio_path, language=language, model_size=model_size, diarize=False
        )

    def transcribe_diarized(
        self,
        audio_path: Path | str,
        *,
        language: str | None = None,
        model_size: str = "auto",
        enrich_with_bible_refs: bool = False,
        min_speakers: int | None = None,
        max_speakers: int | None = None,
    ) -> DiarizedResult:
        """Transcripción + diarización + opcional enrichment con BibleRef."""
        result = self._transcribe_impl(
            audio_path,
            language=language,
            model_size=model_size,
            diarize=True,
            min_speakers=min_speakers,
            max_speakers=max_speakers,
        )
        if not isinstance(result, DiarizedResult):
            raise RuntimeError("Expected DiarizedResult; got " + type(result).__name__)
        if enrich_with_bible_refs:
            result = self._enrich_bible_refs(result)
        return result

    def _transcribe_impl(
        self,
        audio_path: Path | str,
        *,
        language: str | None,
        model_size: str,
        diarize: bool,
        min_speakers: int | None = None,
        max_speakers: int | None = None,
    ) -> TranscriptionResult | DiarizedResult:
        import whisperx

        actual_size = self.model_size if model_size == "auto" else model_size
        device = self.target
        compute_type = "int8" if device == "cpu" else "float16"

        if self._asr_model is None:
            self._asr_model = whisperx.load_model(
                actual_size, device, compute_type=compute_type
            )

        audio = whisperx.load_audio(str(audio_path))
        asr_out = self._asr_model.transcribe(audio, language=language)
        detected_lang = asr_out.get("language", language or "en")

        # Word-level alignment
        if self._align_model is None or self._align_model[1] != detected_lang:
            model_a, metadata = whisperx.load_align_model(
                language_code=detected_lang, device=device
            )
            self._align_model = (model_a, detected_lang, metadata)
        aligned = whisperx.align(
            asr_out["segments"],
            self._align_model[0],
            self._align_model[2],
            audio,
            device,
            return_char_alignments=False,
        )

        if not diarize:
            segments = [
                TranscriptionSegment(start=s["start"], end=s["end"], text=s["text"])
                for s in aligned["segments"]
            ]
            return TranscriptionResult(
                text=" ".join(s.text for s in segments).strip(),
                language=detected_lang,
                duration=audio.shape[0] / 16000.0,
                segments=segments,
            )

        # Diarization
        hf_token = os.environ.get("HF_TOKEN") or os.environ.get(
            "HUGGING_FACE_HUB_TOKEN"
        )
        if not hf_token:
            raise WhisperXDiarizationError(
                "Diarization requires a HuggingFace token. Set HF_TOKEN "
                "env var and accept terms at https://hf.co/pyannote/speaker-diarization-3.1"
            )
        if self._diarize_model is None:
            self._diarize_model = whisperx.DiarizationPipeline(
                use_auth_token=hf_token, device=device
            )
        diarize_segments = self._diarize_model(
            audio, min_speakers=min_speakers, max_speakers=max_speakers
        )
        result_with_speakers = whisperx.assign_word_speakers(diarize_segments, aligned)

        segments_diarized: list[DiarizedSegment] = []
        for s in result_with_speakers["segments"]:
            segments_diarized.append(
                DiarizedSegment(
                    start=s["start"],
                    end=s["end"],
                    text=s["text"],
                    speaker_id=s.get("speaker"),
                )
            )
        speaker_ids = {seg.speaker_id for seg in segments_diarized if seg.speaker_id}
        return DiarizedResult(
            text=" ".join(s.text for s in segments_diarized).strip(),
            language=detected_lang,
            duration=audio.shape[0] / 16000.0,
            segments=segments_diarized,
            speaker_count=len(speaker_ids),
        )

    @staticmethod
    def _enrich_bible_refs(result: DiarizedResult) -> DiarizedResult:
        """Para cada segmento, extrae BibleRef si el texto las menciona."""
        from jw_core.parsers.reference import parse_reference

        enriched: list[DiarizedSegment] = []
        for seg in result.segments:
            refs = parse_reference(seg.text)
            enriched.append(
                DiarizedSegment(
                    start=seg.start,
                    end=seg.end,
                    text=seg.text,
                    speaker_id=seg.speaker_id,
                    bible_refs=tuple(refs) if refs else (),
                )
            )
        return DiarizedResult(
            text=result.text,
            language=result.language,
            duration=result.duration,
            segments=enriched,
            speaker_count=result.speaker_count,
        )
```

- [ ] **Step 3: Run tests, expect PASS o skipped**

Run: `uv run pytest packages/jw-core/tests/test_audio_asr_whisperx.py -v`
Expected: si whisperX instalado, 5 passed; si no, 2 passed (metadata + is_available) + 3 skipped.

- [ ] **Step 4: Commit**

```bash
git add packages/jw-core/src/jw_core/audio/asr_providers/whisperx.py packages/jw-core/tests/test_audio_asr_whisperx.py
git commit -m "feat(jw-core): F64.3 WhisperXProvider with diarization plus BibleRef enrichment"
```

---

### Task 4: Registrar provider en router + CLI

**Files:**
- Modify: `packages/jw-core/src/jw_core/audio/transcription.py` (función `_all_providers`)
- Modify: `packages/jw-cli/src/jw_cli/...` (comando `audio transcribe`)

- [ ] **Step 1: Registrar en `_all_providers()`**

Localizar la función `_all_providers()` en `packages/jw-core/src/jw_core/audio/transcription.py`. Añadir lazy import:

```python
def _all_providers() -> list[type[ASRProvider]]:
    out: list[type[ASRProvider]] = []
    try:
        from jw_core.audio.asr_providers.deepgram import DeepgramASRProvider
        out.append(DeepgramASRProvider)
    except ImportError:
        pass
    try:
        from jw_core.audio.asr_providers.whisper_turbo import WhisperTurboProvider
        out.append(WhisperTurboProvider)
    except ImportError:
        pass
    try:
        from jw_core.audio.asr_providers.whisperx import WhisperXProvider
        out.append(WhisperXProvider)
    except ImportError:
        pass
    try:
        from jw_core.audio.asr_providers.omnilingual import OmnilingualProvider
        out.append(OmnilingualProvider)
    except ImportError:
        pass
    return out
```

> **Decisión re-confirmada**: NO se añade `whisperx` a `DEFAULT_ASR_CHAIN`. El router solo lo selecciona si `JW_ASR_PROVIDER=whisperx` o `name="whisperx"` explícito.

- [ ] **Step 2: Test del router incluye whisperx**

Añadir a `packages/jw-core/tests/test_audio_transcription.py` (o equivalente):

```python
def test_list_asr_providers_includes_whisperx():
    from jw_core.audio.transcription import list_asr_providers

    names = {p["name"] for p in list_asr_providers()}
    # whisperx aparece si la dep está instalada; si no, no aparece
    if __import__("importlib").util.find_spec("whisperx"):
        assert "whisperx" in names


def test_get_asr_provider_by_name_whisperx_when_available():
    from jw_core.audio.transcription import get_asr_provider

    if not __import__("importlib").util.find_spec("whisperx"):
        import pytest
        pytest.skip("whisperx not installed")
    p = get_asr_provider(name="whisperx")
    assert p.name == "whisperx"
```

- [ ] **Step 3: CLI subcommand `jw audio transcribe --diarize`**

Localizar el comando `audio transcribe` en CLI. Si no existe, crear:

```python
@audio_app.command("transcribe")
def cli_transcribe(
    audio_path: Path = typer.Argument(..., help="Ruta al archivo audio"),
    language: str = typer.Option("auto", "--language"),
    provider: str = typer.Option(None, "--provider", help="deepgram|whisper-turbo|whisperx|omnilingual"),
    diarize: bool = typer.Option(False, "--diarize", help="Identificar oradores (requiere whisperx + HF token)"),
    bible_refs: bool = typer.Option(False, "--bible-refs", help="Enriquecer segmentos con BibleRef si los mencionan"),
    output: Path | None = typer.Option(None, "--output", help="Guardar JSON; default stdout"),
) -> None:
    """Transcribe un archivo de audio. Con --diarize identifica oradores."""
    import json
    from jw_core.audio.transcription import get_asr_provider

    lang = None if language == "auto" else language
    asr = get_asr_provider(name=provider, language=lang)

    if diarize:
        if asr.name != "whisperx":
            typer.echo("--diarize requires --provider=whisperx", err=True)
            raise typer.Exit(2)
        result = asr.transcribe_diarized(audio_path, language=lang, enrich_with_bible_refs=bible_refs)
    else:
        result = asr.transcribe(audio_path, language=lang)

    payload = {
        "text": result.text,
        "language": result.language,
        "duration": result.duration,
        "segments": [
            {
                "start": s.start,
                "end": s.end,
                "text": s.text,
                **({"speaker_id": s.speaker_id} if hasattr(s, "speaker_id") else {}),
                **({"bible_refs": [r.display() for r in s.bible_refs]} if hasattr(s, "bible_refs") and s.bible_refs else {}),
            }
            for s in result.segments
        ],
    }
    if hasattr(result, "speaker_count"):
        payload["speaker_count"] = result.speaker_count

    if output:
        output.write_text(json.dumps(payload, ensure_ascii=False, indent=2))
        typer.echo(f"Wrote {output}")
    else:
        typer.echo(json.dumps(payload, ensure_ascii=False, indent=2))
```

- [ ] **Step 4: Run tests router**

Run: `uv run pytest packages/jw-core/tests/test_audio_transcription.py -v`
Expected: tests existentes verdes + 2 nuevos.

- [ ] **Step 5: Commit**

```bash
git add packages/jw-core/src/jw_core/audio/transcription.py packages/jw-cli/src/ packages/jw-core/tests/
git commit -m "feat(jw-cli): F64.4 jw audio transcribe with diarize plus bible-refs"
```

---

### Task 5: MCP tool `transcribe_audio_diarized`

**Files:**
- Modify: `packages/jw-mcp/src/jw_mcp/server.py`
- Modify: `packages/jw-mcp/tests/test_protocol.py`

- [ ] **Step 1: Añadir tool**

```python
@mcp.tool
async def transcribe_audio_diarized(
    audio_path: str,
    language: str | None = None,
    enrich_with_bible_refs: bool = False,
    min_speakers: int | None = None,
    max_speakers: int | None = None,
) -> dict[str, Any]:
    """Transcribe audio identificando oradores y opcionalmente
    enriqueciendo segmentos con referencias bíblicas mencionadas.

    Requiere `[asr-whisperx]` extra y HF_TOKEN env var para descargar el
    modelo de diarización pyannote.

    Args:
        audio_path: ruta absoluta al audio.
        language: ISO code (en/es/pt/...); None auto-detect.
        enrich_with_bible_refs: si True, segmentos cuyo texto mencione
            "Génesis 1:1" o similar reciben `bible_refs: [BibleRef]`.
        min_speakers/max_speakers: hints para diarización.

    Returns:
        Dict con `text`, `language`, `duration`, `speaker_count`,
        `segments: [{start,end,text,speaker_id,bible_refs}]`.
    """
    try:
        from jw_core.audio.asr_providers.whisperx import (
            WhisperXDiarizationError,
            WhisperXProvider,
        )
    except ImportError as exc:
        return {"error": f"asr-whisperx extra not installed: {exc}"}
    try:
        from pathlib import Path
        p = WhisperXProvider()
        if not p.is_available():
            return {"error": "whisperx package not available; install [asr-whisperx] extra"}
        result = p.transcribe_diarized(
            Path(audio_path),
            language=language,
            enrich_with_bible_refs=enrich_with_bible_refs,
            min_speakers=min_speakers,
            max_speakers=max_speakers,
        )
        return {
            "text": result.text,
            "language": result.language,
            "duration": result.duration,
            "speaker_count": result.speaker_count,
            "segments": [
                {
                    "start": s.start,
                    "end": s.end,
                    "text": s.text,
                    "speaker_id": s.speaker_id,
                    "bible_refs": [r.display() for r in s.bible_refs],
                }
                for s in result.segments
            ],
        }
    except WhisperXDiarizationError as exc:
        return {"error": f"diarization unavailable: {exc}"}
    except Exception as exc:
        return {"error": f"{type(exc).__name__}: {exc}"}
```

- [ ] **Step 2: `_EXPECTED_TOOLS` includes nueva**

Añadir `"transcribe_audio_diarized"` al set.

- [ ] **Step 3: Run tests, expect PASS**

```bash
uv run pytest packages/jw-mcp/tests/test_protocol.py -v
```

- [ ] **Step 4: Commit**

```bash
git add packages/jw-mcp/
git commit -m "feat(jw-mcp): F64.5 expose transcribe_audio_diarized MCP tool"
```

---

### Task 6: Guía + ROADMAP + master plan update

**Files:**
- Create: `docs/guias/asr-diarizacion.md`
- Modify: `docs/README.md`, `docs/ROADMAP.md`, master plan

- [ ] **Step 1: Guía operativa**

```markdown
# Diarización ASR con WhisperX (Fase 64)

> Transcribe asambleas, discursos y reuniones identificando quién dice
> qué, con timestamps al nivel de palabra y reconocimiento automático
> de las referencias bíblicas mencionadas.

## Cuándo usar WhisperX vs alternativos

| Necesitas | Usa |
|---|---|
| Transcripción rápida de un audio | `whisper-turbo` (default) |
| Idioma raro (1672 cubiertos) | `omnilingual` (F53) |
| API rápida + buena calidad EN/ES | `deepgram` (requiere API key) |
| **Identificar oradores** | `whisperx` ← esta guía |
| **Word-level timestamps** | `whisperx` ← esta guía |

## Setup

```bash
uv add 'jw-core[asr-whisperx]'
```

Para diarización (identificar oradores):

1. Crear cuenta HuggingFace: https://huggingface.co/join
2. Aceptar términos: https://huggingface.co/pyannote/speaker-diarization-3.1
3. Generar access token: https://huggingface.co/settings/tokens
4. Exportar: `export HF_TOKEN=hf_xxx`

(El token NO se guarda en disco. WhisperX lo usa solo para descargar el
modelo de diarización la primera vez; después corre 100% local.)

## Uso

### CLI

```bash
# Transcripción simple (sin diarización)
jw audio transcribe ~/discurso.wav --provider whisperx --language es

# Con diarización
jw audio transcribe ~/asamblea_60min.wav --provider whisperx --language es --diarize

# Diarización + extracción automática de BibleRef
jw audio transcribe ~/discurso.wav --provider whisperx --language es \
    --diarize --bible-refs --output result.json
```

### Python

```python
from jw_core.audio.asr_providers.whisperx import WhisperXProvider

p = WhisperXProvider()
result = p.transcribe_diarized(
    "/path/to/discurso.wav",
    language="es",
    enrich_with_bible_refs=True,
)
print(f"{result.speaker_count} oradores detectados")
for seg in result.segments:
    refs = ", ".join(r.display() for r in seg.bible_refs)
    print(f"[{seg.speaker_id}] {seg.start:.1f}-{seg.end:.1f}: {seg.text}  refs=[{refs}]")
```

### MCP (Claude)

```
@jw-agent-toolkit transcribe_audio_diarized
  audio_path: /Users/me/asamblea.wav
  language: es
  enrich_with_bible_refs: true
```

## Performance

- **GPU CUDA**: ~10x más rápido que real-time (1 hora audio → 6 min compute).
- **CPU**: ~1-2x real-time (1 hora audio → 30-60 min compute).
- **Memoria**: `large-v3` ~4 GB VRAM; `medium` ~2 GB; `tiny` ~1 GB.

Modelo configurable: `WhisperXProvider(model_size="medium")`.

## Limitaciones

- **Solapamiento de voz**: si dos oradores hablan a la vez, la diarización
  asigna un solo speaker_id al segmento.
- **Audio de baja calidad**: <8kHz sample rate o ruido fuerte degradan
  precision de speaker_id.
- **Modelos solo descargan con conexión**: el primer transcribe_diarized
  baja ~2 GB (`pyannote/speaker-diarization-3.1`). Luego offline.
- **Diferenciación de hermanos**: la diarización NO sabe NOMBRES; etiqueta
  `SPEAKER_00`, `SPEAKER_01`, etc. Para mapear a nombres reales necesitas
  un pass adicional (no incluido en F64).
```

- [ ] **Step 2: docs/README.md y ROADMAP.md updates**

README añade:
```markdown
- [Diarización ASR con WhisperX](guias/asr-diarizacion.md) — Fase 64: transcribe discursos identificando oradores + extracción automática de BibleRef.
```

ROADMAP:
```markdown
## Fase 64 — whisperX ASR provider con diarización ✅

- ✅ `WhisperXProvider` con `transcribe()` (compatibility) y `transcribe_diarized()`.
- ✅ `DiarizedResult`/`DiarizedSegment` extiende dataclasses sin breaking.
- ✅ Enrichment opcional con BibleRef vía `parse_reference()`.
- ✅ CLI `jw audio transcribe --diarize --bible-refs`.
- ✅ MCP tool `transcribe_audio_diarized`.
- ✅ HF token gating con error claro si falta.
- ⬜ Mapeo speaker_id → nombre real (futuro: integration con voiceprint de hermanos del organized-app schedule).
```

- [ ] **Step 3: Marcar F64 ✅ en master plan**

- [ ] **Step 4: Commit final**

```bash
git add docs/
git commit -m "docs(F64): whisperX diarization guide plus ROADMAP entry"
```

---

## Tests resumen

```bash
uv run pytest packages/jw-core/tests/test_audio_diarized_models.py \
              packages/jw-core/tests/test_audio_asr_whisperx.py \
              packages/jw-core/tests/test_audio_transcription.py \
              packages/jw-mcp/tests/test_protocol.py \
              -v --tb=short
```

Con whisperX instalado: ~10 passed. Sin: 4 passed + 6 skipped.

---

## Self-review checklist

- ✅ **Cobertura de spec**: provider impl + diarización + BibleRef enrichment + CLI + MCP tool + token gating + docs.
- ✅ **No placeholders**: cada Step tiene código completo. Sólo se marca para verificar API de `audio_app` Typer si el sub-app no existe.
- ✅ **Consistencia de tipos**: `TranscriptionResult` legacy vs `DiarizedResult` superclase. `DiarizedSegment` extiende `TranscriptionSegment`. Nombres consistentes en provider, router, CLI y MCP.
- ⚠️ **Riesgo HF token**: si CI corre los tests con HF_TOKEN no disponible, los tests de diarización están skipped (marcados con skipif explícito). El CI verde sin diarización es OK.
