# Fase 34 — `audio-premium`: TTS y ASR de alta calidad con triple-target

> **Fecha**: 2026-05-31
> **Estado**: Diseño aprobado (pendiente de implementación)
> **Owner**: Elias
> **Tier**: 1 (núcleo — sube techo de calidad sin romper API)
> **Depende de**: ninguna fase. Aditivo sobre `jw_core.audio.tts` y `jw_core.audio.transcription` existentes.
> **Documento padre**: [`2026-05-31-fases-33-38-overview.md`](2026-05-31-fases-33-38-overview.md)

## Motivación

El stack de audio actual (`jw-core` Fase 11) cubre el caso básico con tres providers TTS (`system`, `edge`, `piper`) más `faster-whisper` base para ASR. Eso fue suficiente cuando el objetivo era "leer un versículo en voz alta" pero queda corto para los usos reales que ya están aterrizando:

1. **Discursos públicos** narrados con calidad de podcast (kokoro/F5).
2. **Clonación de voz personal** opt-in (XTTSv2) para que el hermano lea sus propias notas con su propia voz.
3. **Transcripción de cursos** y reuniones de circuito largas — el modelo `base` se equivoca demasiado y `large-v3-turbo` (lanzado oct 2024) corre ~8× más rápido con casi la misma WER.
4. **Cobertura es/en/pt mínima** con naturalidad — los voces neurales modernas (Kokoro 82M, Eleven v3) son drásticamente mejores que `say`/`espeak`.

Esta fase **añade providers premium** al stack existente sin romper compatibilidad. Los 3 providers actuales se quedan exactamente como están — no se renombran, no se mueven, no se rompe ningún import público.

## Objetivos (orden de prioridad)

1. **Kokoro local como default** cuando el hardware lo permite — fluent es/en/pt en CPU sin red, modelo de 82M params.
2. **API premium opt-in** (ElevenLabs TTS, Deepgram ASR) detrás de env keys, cero impacto si las keys no están.
3. **Voice cloning opt-in** (XTTSv2) detrás de doble flag + disclaimer (alinea con Política #6 del overview: nada que pueda confundirse con voces de hermanos reales sin consentimiento).
4. **F5-TTS experimental** target nvidia primary, mlx fallback — para usuarios con GPU dedicada.
5. **Whisper turbo + auto-select** según VRAM detectada (`torch.cuda.mem_get_info` o `psutil` para MPS).
6. **Sin red en tests** — cada provider real ship un fake hermano determinista (FakeKokoro, FakeXTTS, FakeElevenLabs, FakeDeepgram).

## No-objetivos (boundaries vinculantes)

- **No** entrenar TTS/ASR custom — territorio `jw-finetune`.
- **No** distribuir pesos — todos los modelos locales se descargan al primer uso vía `huggingface_hub` o el SDK del provider; el repo no incluye binarios.
- **No** romper los 3 providers existentes — `SystemTTSProvider`, `EdgeTTSProvider`, `PiperTTSProvider` quedan intactos en `jw_core.audio.tts`.
- **No** clonar voces sin doble opt-in explícito + un `consent.txt` firmado junto al output (mismo patrón anti-emulación que Fase 38).
- **No** auto-detectar GPU NVIDIA en CI — el CI público corre en runners Linux sin GPU; los providers `nvidia` se skippean con `pytest.mark.skipif`.

## Arquitectura

```
packages/jw-core/src/jw_core/audio/
├── tts.py                       # EXISTING — ABC TTSProvider + system/edge/piper
│                                # SOLO modificado para añadir nuevos providers al _PROVIDERS
│                                # registry y honrar JW_TTS_PROVIDER env.
├── tts_providers/               # NEW subpackage
│   ├── __init__.py              # re-exporta providers nuevos
│   ├── kokoro.py                # KokoroTTSProvider (CPU first, mlx/nvidia accel)
│   ├── xtts.py                  # XTTSv2Provider (voice cloning opt-in)
│   ├── f5.py                    # F5TTSProvider (nvidia primary, mlx exp)
│   ├── elevenlabs.py            # ElevenLabsProvider (API)
│   └── fakes.py                 # FakeKokoro, FakeXTTS, FakeElevenLabs, FakeF5
├── transcription.py             # EXISTING — faster-whisper base
│                                # SOLO modificado para añadir model_size auto-select
│                                # y registrar provider chain.
├── asr_providers/               # NEW subpackage
│   ├── __init__.py
│   ├── whisper_turbo.py         # WhisperTurboProvider (faster-whisper + large-v3-turbo)
│   ├── deepgram.py              # DeepgramProvider (API streaming)
│   └── fakes.py                 # FakeWhisperTurbo, FakeDeepgram
└── hardware.py                  # NEW — detect_target() / available_vram_gb()
                                 # auto-select chain
```

### Reglas duras de diseño

1. Cada provider nuevo extiende **la ABC ya existente** `jw_core.audio.tts.TTSProvider`. No se crea una ABC paralela.
2. Cada provider implementa `is_available()` que **no hace red**: chequea import del SDK + env keys + binarios.
3. La factory `get_tts_provider(name=None)` se modifica para honrar `JW_TTS_PROVIDER` env y la chain default `kokoro_local → edge → system → elevenlabs (si key) → piper`.
4. Cada provider declara `target: Literal["api", "nvidia", "mlx", "cpu"]` para que la factory pueda filtrar por hardware.
5. **Sin imports a nivel de módulo** de SDKs pesados (`torch`, `coqui-tts`, `f5_tts`): todos los imports son perezosos dentro de `synthesize()` o `is_available()`.
6. Fakes son **clases hermanas en `fakes.py`**, no fixtures pytest — disponibles también desde código de usuario para tests downstream.

## TTS providers nuevos

### `KokoroTTSProvider`

- **Modelo**: `hexgrad/Kokoro-82M` via `huggingface_hub`.
- **Backend**: `onnxruntime` para CPU; `onnxruntime-gpu` si NVIDIA detectada; `mlx` para Apple Silicon (experimental, fallback a CPU).
- **Languages**: en, es, pt, fr, de, it, ja, zh.
- **Voice**: `name` interno del modelo (por idioma) o custom embedding.
- **Latency**: ~150ms/oración en M3 CPU.
- **Default chain position**: **primero** si está instalado.
- **Coste**: $0, local.

### `XTTSv2Provider`

- **Modelo**: `coqui/XTTS-v2` via `coqui-tts` (forked fork mantenido).
- **Voice cloning**: requiere `voice_sample_path` (clip de 6-10s) **+ env `JW_XTTS_CLONE_CONSENT=1`** + escribir `consent.txt` al lado del output.
- **Languages**: 17 incl. en/es/pt/fr/de/it/ja/ko/zh/ar/ru/tr.
- **Target primario**: nvidia / mlx. CPU funciona pero ~5× real-time.
- **No** se incluye en chain default — `is_available()` requiere flag explícito.

### `F5TTSProvider`

- **Modelo**: `SWivid/F5-TTS` via `f5-tts` PyPI (cuando esté estable) o local checkout.
- **Target primario**: nvidia. MLX experimental vía `mlx-f5-tts` si el usuario lo instaló manualmente.
- **Quality**: mejor naturalidad open-source 2026 (TTS Arena).
- **Languages**: en (oficial), es/pt vía fine-tunes de comunidad — declaramos `languages_supported = {"en"}` y nada más para evitar over-promise.

### `ElevenLabsProvider`

- **API**: `elevenlabs` SDK si está instalado, sino `httpx` directo a `api.elevenlabs.io/v1/text-to-speech/{voice_id}`.
- **Auth**: `ELEVENLABS_API_KEY` env. Si no está, `is_available() = False`.
- **Languages**: 29 incl. todos los que necesitamos.
- **Default voice**: env `ELEVENLABS_VOICE_ID` o fallback `21m00Tcm4TlvDq8ikWAM` (Rachel).
- **Coste**: pago por carácter — documentado en guía.

## ASR providers nuevos

### `WhisperTurboProvider`

- Extiende el patrón de `transcription.py` pero como clase con `is_available()` + `transcribe()`.
- **Modelo default**: `large-v3-turbo` cuando `available_vram_gb() ≥ 8`. Fallback chain: `large-v3-turbo` → `medium` → `small` → `base` → `tiny`.
- **Auto-select**: nuevo helper `recommend_model_size() -> str`:
  - `torch.cuda.mem_get_info()` si hay CUDA.
  - `psutil.virtual_memory().available / 1024**3` si MPS (Apple) — aprox dado que MPS comparte con sistema.
  - Si no detecta GPU, devuelve `base`.
- **Backwards-compat**: `transcribe_file()` existente sigue funcionando; recibe `model_size="auto"` como nuevo default que llama al recommender.

### `DeepgramProvider`

- **API**: `deepgram-sdk` si instalado, sino `httpx` POST multipart a `api.deepgram.com/v1/listen`.
- **Auth**: `DEEPGRAM_API_KEY`. Sin key → `is_available() = False`.
- **Streaming**: expone `transcribe_stream(audio_iter)` además de `transcribe_file()`.
- **Languages**: en/es/pt + 35 más, con detección automática.

## Auto-detect chain

Función helper `jw_core.audio.hardware.detect_target() -> Literal["api","nvidia","mlx","cpu"]`:

```python
def detect_target() -> Literal["api", "nvidia", "mlx", "cpu"]:
    """Detect the strongest local accelerator available. API last (network)."""

    if shutil.which("nvidia-smi"):
        return "nvidia"
    if sys.platform == "darwin" and platform.machine() == "arm64":
        return "mlx"
    return "cpu"
```

La chain default de TTS (codificada en `tts.py`):

```python
DEFAULT_TTS_CHAIN = [
    "kokoro_local",        # if HF + onnxruntime installed
    "edge",                # if edge-tts installed (network)
    "system",              # always works (say/espeak/powershell)
    "elevenlabs",          # if ELEVENLABS_API_KEY set
    "piper",               # if piper binary installed
]
```

Override vía `JW_TTS_PROVIDER` env. Si `JW_TTS_PROVIDER=kokoro_local` y no está disponible, **error explícito** (no fallback silencioso) para que el usuario sepa qué falta.

## Política de tests sin red

Cada provider nuevo viene con su fake hermano. Los tests **no instancian el provider real** — instancian el Fake. El provider real solo se valida con un test `@pytest.mark.skipif(not provider.is_available())` que pasa silenciosamente en CI público.

```python
# Ejemplo: test_tts_kokoro.py
def test_kokoro_synthesize_writes_wav(tmp_path):
    provider = FakeKokoroTTS()                 # NO red, NO huggingface_hub
    out = provider.synthesize(
        "Hola mundo", voice=None, language="es",
        output_path=tmp_path / "hello.wav",
    )
    assert out.exists()
    assert out.suffix == ".wav"
    assert out.stat().st_size > 0              # fake escribe header WAV mínimo válido
```

## Modelos (Pydantic-free, dataclasses + ABC)

Reutilizamos `TTSProvider` ABC existente. Para ASR formalizamos una ABC nueva en `asr_providers/__init__.py`:

```python
class ASRProvider(ABC):
    name: str
    target: Literal["api", "nvidia", "mlx", "cpu"]
    languages_supported: set[str] = set()

    @abstractmethod
    def is_available(self) -> bool: ...

    @abstractmethod
    def transcribe(
        self,
        audio_path: Path,
        *,
        language: str | None = None,
        model_size: str = "auto",
    ) -> TranscriptionResult: ...
```

`TranscriptionResult` ya existe (`transcription.py`); se reutiliza.

## Integración con el resto del toolkit

### CLI (`jw-cli`)

Comandos `jw say` y `jw transcribe` (Fase 11) **ya existen** — solo se cambia el default chain. Nuevos flags:

```
jw say "Hola" --provider kokoro                  # forzar provider
jw say "Hola" --voice af_bella                   # voice de Kokoro
jw transcribe audio.mp3 --model auto             # nuevo default
jw transcribe audio.mp3 --model large-v3-turbo   # explícito
jw transcribe audio.mp3 --provider deepgram      # API streaming
```

### MCP (`jw-mcp`)

Las herramientas `synthesize_speech` y `transcribe_audio` existentes ganan dos params opcionales: `provider: str | None = None` y `voice: str | None = None`. Sin cambios en el contrato — solo additive params con defaults.

### CI

No se añade ningún job nuevo. Los nuevos tests corren dentro del job `test` actual y todos usan Fakes. Los providers reales (Kokoro/XTTS/F5/EL/Deepgram) están marcados `@pytest.mark.skipif(not <provider>().is_available())`.

## Variables de entorno nuevas

| Variable | Default | Efecto |
|---|---|---|
| `JW_TTS_PROVIDER` | (none) | Override de la chain. Valores: `kokoro_local`, `edge`, `system`, `piper`, `elevenlabs`, `xtts`, `f5` |
| `JW_TTS_TARGET` | (auto) | Force target: `cpu`, `mlx`, `nvidia`, `api` |
| `ELEVENLABS_API_KEY` | (none) | Habilita ElevenLabsProvider |
| `ELEVENLABS_VOICE_ID` | (Rachel) | Voice id por defecto |
| `DEEPGRAM_API_KEY` | (none) | Habilita DeepgramProvider |
| `JW_XTTS_CLONE_CONSENT` | (none) | Requerido para clonación XTTS |
| `JW_KOKORO_MODEL_REPO` | `hexgrad/Kokoro-82M` | Override del repo HF |
| `JW_PIPER_MODEL` | (none) | Se mantiene |

## Dependencias opcionales (pyproject extras)

```toml
[project.optional-dependencies]
tts-kokoro = [
    "huggingface_hub>=0.24.0",
    "onnxruntime>=1.19.0",
    "soundfile>=0.12.1",
    "numpy>=1.26.0",
]
tts-xtts = [
    "coqui-tts>=0.24.0",         # mantained fork
]
tts-f5 = [
    "f5-tts>=0.4.0",
]
tts-elevenlabs = [
    "elevenlabs>=1.5.0",
]
asr-deepgram = [
    "deepgram-sdk>=3.7.0",
]
asr-turbo = [
    "faster-whisper>=1.1.0",     # bump for large-v3-turbo support
]
audio-premium = [
    # bundle de todo lo anterior LOCAL
    "jw-core[tts-kokoro,asr-turbo]",
]
```

## Riesgos y mitigaciones

| # | Riesgo | Mitigación |
|---|---|---|
| 1 | Kokoro descarga ~310MB al primer uso → CI lento | Mock HF en tests; documentar warm-up en guía |
| 2 | XTTS voice cloning abuso | Doble flag + consent.txt + disclaimer en guía Política #6 |
| 3 | ElevenLabs key se loguea | Nunca logear key; sanitizar logs como hacemos con `ANTHROPIC_API_KEY` |
| 4 | F5 PyPI inestable | Fail-soft: `is_available() = False` si `import f5_tts` falla. Documentar como experimental |
| 5 | faster-whisper API rompió entre 1.0 y 1.1 | Pin `>=1.1.0`; tests aislan via Fake |
| 6 | MPS VRAM detection no-confiable | Documentar; fallback a `medium` si la detección falla |
| 7 | `is_available()` hace red accidental | Tests verifican que `is_available()` no abre sockets (`socket.socket` mock) |
| 8 | Romper backwards-compat de `transcribe_file()` | `model_size="auto"` es nuevo default pero acepta strings antiguos exactos |

## Métricas de éxito

- ✅ `jw say "Hola mundo, soy Jehová" --provider kokoro` produce audio fluent es sin red, en <500ms en M3.
- ✅ Chain default en máquina nueva (sin Kokoro instalado) cae a edge → produce audio sin error.
- ✅ `jw transcribe audio_5min.mp3 --model auto` selecciona `large-v3-turbo` si hay 8GB+ VRAM, `base` si no.
- ✅ 5 tests nuevos por provider (TTS) + 3 por provider (ASR) — todos con Fakes, 0 red.
- ✅ `pytest packages/jw-core/tests/test_tts_*.py test_asr_*.py test_audio_factory.py` < 5s.
- ✅ Documentado en `docs/guias/audio-premium.md`.
- ✅ Sin regresiones en los 1649 tests existentes.

## Cómo verificar al cerrar

```bash
# 1. Install opt-in deps
uv sync --all-packages
uv pip install -e "packages/jw-core[audio-premium]"

# 2. Tests offline
.venv/bin/python -m pytest packages/jw-core/tests/test_tts_*.py packages/jw-core/tests/test_asr_*.py packages/jw-core/tests/test_audio_factory.py -v

# 3. Smoke kokoro local
uv run jw say "Hola mundo" --provider kokoro --out /tmp/hola.wav

# 4. Smoke whisper turbo (necesita un .mp3 de prueba)
uv run jw transcribe tests/fixtures/audio/sample_es.mp3 --model auto

# 5. Smoke ElevenLabs (opcional, requiere key)
ELEVENLABS_API_KEY=sk-... uv run jw say "Hello" --provider elevenlabs --out /tmp/eleven.mp3
```

## Plan de implementación

Spec hijo: [`docs/superpowers/plans/2026-05-31-fase-34-audio-premium-plan.md`](../plans/2026-05-31-fase-34-audio-premium-plan.md).

13 tareas TDD encadenadas: hardware detect → fakes → kokoro → xtts → f5 → elevenlabs → whisper turbo → deepgram → factory update → CLI flags → MCP params → guía → audit final.
