# Diarización ASR con WhisperX (Fase 64)

> Transcribe asambleas, discursos y reuniones identificando quién dice
> qué, con timestamps al nivel de palabra y reconocimiento automático
> de las referencias bíblicas mencionadas.

## Cuándo usar WhisperX vs alternativos

| Necesitas | Usa |
|---|---|
| Transcripción rápida de un audio | `whisper_turbo` (default local) |
| Idioma raro (1672 cubiertos) | `omnilingual` (F53) |
| API rápida + buena calidad EN/ES | `deepgram` (requiere API key) |
| **Identificar oradores** | `whisperx` ← esta guía |
| **Word-level timestamps** | `whisperx` ← esta guía |

WhisperX está fuera de `DEFAULT_ASR_CHAIN` a propósito: el modelo
`pyannote/speaker-diarization-3.1` pesa ~2 GB y no se descarga hasta
que se selecciona explícitamente.

## Setup

```bash
uv add 'jw-core[asr-whisperx]'
```

Para diarización (identificar oradores):

1. Crear cuenta HuggingFace: <https://huggingface.co/join>
2. Aceptar términos: <https://huggingface.co/pyannote/speaker-diarization-3.1>
3. Generar access token: <https://huggingface.co/settings/tokens>
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

> El comando legacy `jw transcribe` sigue existiendo y se mantiene como
> entrada mínima. `jw audio transcribe` añade `--diarize` y `--bible-refs`.

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

```text
@jw-agent-toolkit transcribe_audio_diarized
  audio_path: /Users/me/asamblea.wav
  language: es
  enrich_with_bible_refs: true
```

Devuelve un dict con:

```json
{
  "text": "...",
  "language": "es",
  "duration": 3600.0,
  "speaker_count": 3,
  "segments": [
    {
      "start": 0.0,
      "end": 4.2,
      "text": "Bienvenidos hermanos. Leamos Génesis 1:1.",
      "speaker_id": "SPEAKER_00",
      "bible_refs": ["Genesis 1:1"]
    }
  ]
}
```

## Modelos de datos

WhisperX devuelve dataclasses retrocompatibles con la API estable de
`jw_core.audio.transcription`:

- `DiarizedSegment(TranscriptionSegment)` añade `speaker_id` +
  `bible_refs: tuple[BibleRef, ...]`.
- `DiarizedResult(TranscriptionResult)` añade `speaker_count` y
  estrecha `segments` a `list[DiarizedSegment]`.

Cualquier consumidor que espere `TranscriptionResult` sigue funcionando
sin cambios — los campos adicionales se ignoran de forma natural.

## Performance

- **GPU CUDA**: ~10x más rápido que real-time (1 h audio → ~6 min compute).
- **CPU**: ~1-2x real-time (1 h audio → 30-60 min compute).
- **Memoria**: `large-v3` ~4 GB VRAM; `medium` ~2 GB; `tiny` ~1 GB.

Modelo configurable: `WhisperXProvider(model_size="medium")`.

## Limitaciones

- **Solapamiento de voz**: si dos oradores hablan a la vez, la
  diarización asigna un solo `speaker_id` al segmento.
- **Audio de baja calidad**: <8 kHz sample rate o ruido fuerte degradan
  la precisión del `speaker_id`.
- **Modelos solo descargan con conexión**: el primer `transcribe_diarized`
  baja ~2 GB (`pyannote/speaker-diarization-3.1`). Luego corre offline.
- **Diferenciación de hermanos**: la diarización NO sabe NOMBRES; etiqueta
  `SPEAKER_00`, `SPEAKER_01`, etc. Para mapear a nombres reales necesitas
  un pass adicional (no incluido en F64; futuro: voiceprint del
  organized-app schedule, F51).

## Manejo de errores

`WhisperXDiarizationError(RuntimeError)` se lanza si falta `HF_TOKEN`
al pedir `transcribe_diarized()`. El tool MCP lo captura y devuelve
`{"error": "diarization unavailable: ..."}` para que el caller no
reciba un stack trace.
