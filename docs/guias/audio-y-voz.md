# Audio y voz (Módulo 3 — Fase 13)

> Cierra el ítem #3 de [VISION.md](../VISION.md): TTS multilenguaje, búsqueda en transcripciones de JW Broadcasting, dictado con Whisper local.

## Decisión de arquitectura: tres providers pluggables

| Provider | Modo | Calidad | Coste | Latencia | Idiomas |
|---|---|---|---|---|---|
| `system` | Local CLI (`say`/`espeak`/PowerShell) | Baja | $0 | Inmediato | 8+ |
| `edge` | Cloud (Microsoft Edge TTS, gratis) | Alta | $0 (sin API key) | ~1-2 s | 12+ |
| `piper` | Local (CTranslate2 + onnx) | Media-alta | $0 | Bajo (CPU) | 6+ |

Auto-detección al pedir `get_tts_provider()`. El usuario puede forzar uno con `provider=...`. No hay lock-in: si edge-tts un día deja de funcionar, sistema y piper siguen sirviendo.

```python
from jw_core.audio import synthesize_to_file

synthesize_to_file(
    "Hola mundo",
    "out.wav",
    language="es",
)  # auto-detecta
```

Variables de entorno:
- `JW_PIPER_MODEL=/path/voice.onnx` — voz piper por defecto.

## Transcripción local (Whisper)

`jw_core.audio.transcription.transcribe_file(audio_path)`. Requiere `faster-whisper` instalado (opcional).

```python
from jw_core.audio import transcribe_file

result = transcribe_file("note.wav", model_size="base", language="es")
print(result.text)
for seg in result.segments:
    print(f"{seg.start:.1f}-{seg.end:.1f}: {seg.text}")
```

Real-Time Factor estimado (M2/M3 CPU):
- `tiny` ~0.1×
- `base` ~0.2×
- `small` ~0.4×
- `medium` ~0.9×
- `large-v3` ~2.0×

## Índice de JW Broadcasting

VISION.md: "Búsqueda en transcripciones de JW Broadcasting (videos + sermones)".

**Capas:**
1. `parse_vtt(text)` → lista de `VTTSegment(start, end, text)`. Maneja `.vtt`, `.srt`, removes `<v>`/`<b>` tags.
2. `BroadcastingIndex(path)` → SQLite + FTS5 sobre los segmentos. Default en `~/.jw-agent-toolkit/broadcasting.db` (override `JW_BROADCASTING_INDEX`).
3. `index_vtt_file(idx, "path.vtt", video_id=..., title=..., source_url=...)` → ingest end-to-end.
4. `search(query, language=..., top_k=...)` → ranked results vía SQLite FTS rank.
5. `deeplink_for_segment(url, start)` → URL con `?t=Ns` para saltar al frame.

**Pipeline típico:**
```python
from jw_core.audio.broadcasting import BroadcastingIndex, index_vtt_file

with BroadcastingIndex() as idx:
    index_vtt_file(idx, "resurrection.vtt",
                   video_id="hope-101",
                   title="The Hope of Resurrection",
                   language="en",
                   source_url="https://tv.jw.org/hope-101")
    hits = idx.search("resurrection hope")
    for h in hits:
        print(h["title"], h["start"], h["text"][:80])
```

## Agente unificado

`jw_agents.audio_helper`:
- `read_verse_aloud(book_num, chapter, verse, output_path=...)` — fetch + TTS + finding con `audio_path`.
- `read_article_aloud(url, output_path=...)` — N párrafos a audio.
- `search_broadcasting(query)` — `AgentResult` con findings (cada uno con deeplink `?t=Ns`).

## Herramientas MCP nuevas

| Tool | Descripción |
|---|---|
| `list_tts_engines` | Inventario de providers TTS disponibles |
| `read_verse_aloud` | Sintetiza un versículo a `.wav`/`.mp3` |
| `read_article_aloud` | Sintetiza un artículo de WOL |
| `search_broadcasting` | FTS sobre el índice de subtitles |
| `index_broadcasting_vtt` | Añade una VTT al índice |

## Privacidad / opt-in

- Todo el TTS provider `system` y `piper` se ejecuta en local sin red.
- `edge` envía texto al cloud de Microsoft; el usuario lo elige explícitamente o el toolkit lo detecta como fallback. Para uso 100% local instala `piper-tts` o usa `system`.

## Tests

`packages/jw-core/tests/test_audio_module.py`:

- Registry de TTS providers (los 3 declarados aparecen).
- VTT parser: timestamps en formato `HH:MM:SS.mmm`, strip de tags HTML.
- FTS5: index_video + search round-trip, overwrite por reindex, vtt-roundtrip.
- Deeplink: añade `?t=Ns` o `&t=Ns` según presencia de query string.
- RTF: estimaciones monotónicamente crecientes.

```bash
uv run pytest packages/jw-core/tests/test_audio_module.py -v
```

## Cómo extender

- **Nuevo provider TTS:** subclase `TTSProvider`, agrégalo a `_PROVIDERS` en `tts.py`.
- **Nuevo idioma en `edge`:** añade entrada a `DEFAULT_VOICES`.
- **Búsqueda híbrida (BM25 + embedding) en broadcasting:** envolver `BroadcastingIndex` y delegar embeddings a `jw_rag.VectorStore` reusando `chunk_paragraphs` sobre los segmentos.
