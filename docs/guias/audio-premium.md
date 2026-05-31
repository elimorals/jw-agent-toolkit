# Audio premium — TTS y ASR de alta calidad

Esta guía explica cómo usar los providers nuevos añadidos en Fase 34.
Los providers originales (`system`, `edge`, `piper`) siguen funcionando
exactamente igual; lo aquí descrito es opt-in.

## Instalación rápida

```bash
# Stack local recomendado (Kokoro TTS + Whisper Turbo ASR)
uv pip install -e "packages/jw-core[audio-premium]"

# Solo TTS premium local + ElevenLabs
uv pip install -e "packages/jw-core[tts-premium]"

# Solo ASR premium (Whisper Turbo + Deepgram)
uv pip install -e "packages/jw-core[asr-premium]"
```

## TTS providers

| Provider | Comando | Coste | Network | Notas |
|---|---|---|---|---|
| `kokoro_local` | `jw say "..." --provider kokoro_local` | $0 | No | Recomendado por defecto |
| `edge` | `jw say "..." --provider edge` | $0 | Sí | Voces neurales de MS |
| `system` | `jw say "..." --provider system` | $0 | No | `say`/`espeak` |
| `piper` | `jw say "..." --provider piper` | $0 | No | Requiere `.onnx` |
| `elevenlabs` | `jw say "..." --provider elevenlabs` | $$ | Sí | Necesita `ELEVENLABS_API_KEY` |
| `xtts` | `jw say "..." --provider xtts --voice sample.wav` | $0 | No | Doble opt-in obligatorio |
| `f5` | `jw say "..." --provider f5` | $0 | No | Experimental, requiere NVIDIA |

## ASR providers

```bash
# Auto-select (recomendado): elige large-v3-turbo si tienes >=8GB VRAM
jw transcribe audio.mp3 --model auto

# Forzar tamaño
jw transcribe audio.mp3 --model large-v3-turbo
jw transcribe audio.mp3 --model base

# API (streaming, mejor para reuniones largas)
DEEPGRAM_API_KEY=dg-... jw transcribe audio.mp3 --provider deepgram
```

## Clonación de voz (XTTSv2)

Esta característica es opt-in **doble** por razones éticas:

1. La librería `coqui-tts` debe estar instalada (`jw-core[tts-xtts]`).
2. El env `JW_XTTS_CLONE_CONSENT=1` debe estar presente.
3. Se debe pasar un sample WAV de 6-10s como `--voice`.

Cada output viene acompañado de un `*.consent.txt` documentando la
clonación. Política #6 del overview de fases 33-38 establece que ninguna
voz clonable de un hermano puede usarse sin consentimiento archivable.

## Variables de entorno

Ver la sección homónima en el spec
`docs/superpowers/specs/2026-05-31-fase-34-audio-premium-design.md`.

## Troubleshooting

- **Kokoro descarga lenta**: el modelo (~310MB) se cachea en
  `~/.cache/huggingface`. Ejecuta `jw say "warmup" --provider kokoro_local` una
  sola vez después de instalar.
- **`is_available()` devuelve `False` con la key puesta**: confirma que el
  env está exportado en el shell donde corres `jw` (`echo $ELEVENLABS_API_KEY`).
- **F5 falla en MLX**: F5-MLX es experimental. Usa Kokoro en M3/M4.
