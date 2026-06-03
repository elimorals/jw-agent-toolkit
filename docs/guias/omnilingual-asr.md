---
title: "Omnilingual ASR para 1672 idiomas (Fase 53)"
description: "Provider Meta Apache 2.0 vía venv Python 3.12 dedicado. Quechua, Kinyarwanda, Aymara, Guaraní confirmados."
date: "2026-06-02"
---

# Guía — Omnilingual ASR para 1672 idiomas (Fase 53)

> Transcribir audio de jw-broadcast, asambleas, Salón del Reino o
> grabaciones personales en cualquiera de **1672 idiomas** soportados por
> el modelo open-source de Meta (Apache 2.0), incluyendo cientos de
> lenguas low-resource (quechua, kinyarwanda, aymara, guaraní, lingala,
> yoruba, twi…) que Deepgram y Whisper-large-v3 no cubren con calidad
> usable.

## Por qué este proveedor existe

| Capacidad | Deepgram | Whisper-large-v3 | **Omnilingual** |
|---|---|---|---|
| Idiomas | ~16 | ~99 | **1672** |
| Licencia | API comercial | MIT | Apache 2.0 |
| Local-first | ❌ (cloud) | ✅ | ✅ |
| Mac M1/M2 16GB | n/a | con cuantización | sí (300M-CTC, 4-bit MLX) |
| Streaming nativo | ✅ | ❌ | ❌ |
| Cap. en low-resource | bajo | medio-bajo | **alto** |

Para el ecosistema JW, el cambio relevante es que jw.org publica en
~960 idiomas y jw-broadcast transmite asambleas/discursos en muchos más.
Hasta F53 no había forma de transcribir esos audios. Ahora sí.

## Arquitectura: por qué hay un venv aparte

`omnilingual-asr` depende de `fairseq2`, que **no publica wheels para
Python 3.13** (sólo cp310/cp311/cp312). El toolkit es 3.13. Tres caminos
considerados:

1. **Bajar todo el toolkit a 3.12.** Regresión arquitectónica: 11 paquetes
   del workspace, código que usa `type` PEP-695 y otras features 3.13.
2. **Compilar fairseq2 desde fuente para 3.13.** Complejo, frágil, podría
   no funcionar.
3. **venv-per-feature** (elegido): el toolkit sigue en 3.13, pero
   `OmnilingualProvider` instala un venv dedicado en 3.12 dentro de
   `~/.jw-core/omnilingual/venv` y dispara un script worker via
   `subprocess.run(...)` con I/O por JSON.

### Costo y trade-offs

- **Latencia añadida**: ~300 ms por transcripción (cold-start del
  intérprete 3.12). Despreciable frente al modelo (segundos a minutos
  por clip).
- **No sirve para streaming**: si tu caso es subtítulos en vivo, sigue
  con Deepgram o un provider con streaming nativo. Omnilingual sólo
  hace batch (cap 40s en variantes base, ~15min en
  `omniASR_LLM_Unlimited_*_v2`).
- **Beneficio**: la base de código del toolkit no se ata a la cadencia
  de soporte cp313 de fairseq2. El día que llegue, se cambia el
  `subprocess.run` por `import` y la API pública (`provider.transcribe()`)
  no cambia.

```
┌─────────────────────────────────────────────────────────┐
│ toolkit (Python 3.13)                                    │
│                                                          │
│   from jw_core.audio.transcription import get_asr_provider│
│   provider = get_asr_provider(language="qu")             │
│   ↓                                                       │
│   OmnilingualProvider.transcribe(audio, language="qu")   │
│                       │                                   │
│                       │ subprocess.run([venv/bin/python,  │
│                       │   omnilingual_worker.py,          │
│                       │   --audio ..., --lang quy_Latn])  │
│                       ↓                                   │
└───────────────────────┼──────────────────────────────────┘
                        │
┌───────────────────────▼──────────────────────────────────┐
│ ~/.jw-core/omnilingual/venv  (Python 3.12)                │
│                                                            │
│   omnilingual_worker.py                                    │
│     from omnilingual_asr.models.inference.pipeline ...    │
│     pipeline.transcribe([audio], lang=["quy_Latn"])       │
│   ↓                                                        │
│   print(json.dumps({"text": "...", "language": "..."}))    │
└────────────────────────────────────────────────────────────┘
```

El worker script NO importa `jw_core`. Eso es deliberado: mantiene el
venv 3.12 mínimo y permite que sea instalado/actualizado independiente.

## Bootstrap

### Prerequisitos del sistema

`fairseq2` carga `libsndfile` con `dlopen` en import time. Si no está,
el primer call falla con `OSError: fairseq2 requires libsndfile`.

```bash
# macOS
brew install libsndfile

# Debian/Ubuntu
apt install libsndfile1
```

### Python 3.12

Necesitas un Python 3.12 disponible en el sistema (el toolkit sigue
ejecutándose en 3.13). En macOS:

```bash
brew install python@3.12
```

### Instalación del venv

```bash
jw omnilingual install
```

El comando:

1. Localiza `python3.12` en el PATH.
2. Crea `~/.jw-core/omnilingual/venv` con `python3.12 -m venv`.
3. Instala `omnilingual-asr` + dependencias (~3 GB de wheels: torch 2.8,
   torchaudio 2.8, fairseq2 0.6, polars, numba, etc.).
4. Fuerza `torch==2.8.0 torchaudio==2.8.0` para alinear ABI (la
   resolución libre pickea torchaudio 2.11 que segfaultea contra
   torch 2.8).

### Verificación

```bash
jw omnilingual status
#  venv dir                    /Users/.../venv
#  venv python                 /Users/.../venv/bin/python
#  python exists               yes
#  omnilingual-asr importable  yes
#  default model card          omniASR_CTC_300M
```

## Uso

### Vía CLI

```bash
# Verificar que un idioma está soportado (1672 codes, formato FLORES-200)
jw omnilingual supports kin_Latn
# → yes — kin_Latn is supported

jw omnilingual supports qu_Latn
# → no — qu_Latn is not in the supported list
# (los códigos JW MEPS no son FLORES. Usa el mapeo abajo.)

# Transcribir
jw omnilingual transcribe asamblea.wav --lang qu --model omniASR_CTC_300M
```

### Vía Python (provider directo)

```python
from pathlib import Path
from jw_core.audio.asr_providers.omnilingual import OmnilingualProvider

provider = OmnilingualProvider(model_card="omniASR_CTC_300M")
if not provider.is_available():
    raise RuntimeError("Run `jw omnilingual install` first")

result = provider.transcribe(Path("asamblea.wav"), language="qu")
print(result.text)
print(result.language)  # "quy_Latn" (FLORES tras normalizar)
```

### Vía router F55.1 (recomendado)

El router automático selecciona Omnilingual cuando el idioma no está en
otros providers:

```python
from jw_core.audio.transcription import get_asr_provider

# Inglés → Deepgram (si DEEPGRAM_API_KEY está set)
provider = get_asr_provider(language="en")  # → DeepgramProvider

# Quechua → Omnilingual (Deepgram no lo soporta)
provider = get_asr_provider(language="qu")  # → OmnilingualProvider
```

### Vía MCP (Claude Desktop / Code)

La tool `transcribe_audio` ya está conectada al router F55.1:

```
mcp.tools.transcribe_audio(audio_path="...", language="qu")
# Returns: {"text": "...", "language": "quy_Latn", "provider": "omnilingual"}
```

## Mapeo ISO ↔ FLORES

`OmnilingualProvider._normalize_language()` traduce ISO-639-1 a FLORES-200
para los idiomas relevantes. El módulo lleva un mapeo curado para los
casos JW prioritarios:

| ISO | FLORES | Lengua |
|---|---|---|
| `qu` | `quy_Latn` | Quechua de Ayacucho |
| `ay` | `ayr_Latn` | Aymara central |
| `gn` | `grn_Latn` | Guaraní |
| `rw` | `kin_Latn` | Kinyarwanda |
| `sw` | `swh_Latn` | Swahili |
| `ln` | `lin_Latn` | Lingala |
| `yo` | `yor_Latn` | Yoruba |
| `ig` | `ibo_Latn` | Igbo |
| `ha` | `hau_Latn` | Hausa |
| `zu` | `zul_Latn` | Zulu |
| `xh` | `xho_Latn` | Xhosa |
| `am` | `amh_Ethi` | Amharic |
| (los high-resource) | `eng_Latn`, `spa_Latn`, … | |

Si tu caller ya pasa FLORES (`que_Latn`, `kin_Latn`, …), el provider lo
acepta tal cual. Para el resto de los 1672 idiomas, pasa el código
FLORES directamente — el provider sólo intenta normalizar si NO ve un
`_` en el código.

## Modelos disponibles

Setea con `OMNILINGUAL_MODEL_CARD` env var o `--model` flag:

| Model card | Tamaño | Cap. audio | Hardware mínimo |
|---|---|---|---|
| `omniASR_CTC_300M` | 300M | 40s | Mac M1/M2 8GB |
| `omniASR_CTC_1B` | 1B | 40s | Mac M1/M2 16GB |
| `omniASR_CTC_3B` | 3B | 40s | M-series 32GB |
| `omniASR_LLM_300M_v2` | 300M | 40s | Mac M1/M2 8GB |
| `omniASR_LLM_7B_v2` | 7B | 40s | GPU CUDA/M-series 64GB |
| `omniASR_LLM_Unlimited_7B_v2` | 7B | **~15 min** | GPU CUDA/M-series 64GB |

Default: `omniASR_CTC_300M` — el "Mac-friendly" para empezar.

Para audios largos (asambleas completas), usar `Unlimited_7B_v2` en un
servidor con GPU. Para clips cortos (versículos, fragmentos),
`CTC_300M` basta.

## Caso de uso end-to-end: indexar broadcast en idioma minoritario

Combinando F53 + F55.1 + F55.8:

```python
from pathlib import Path
from jw_core.audio.broadcasting import BroadcastingIndex, transcribe_and_index_audio

index = BroadcastingIndex(Path("~/jw-broadcast.db").expanduser())

# Una asamblea de zona en quechua: el router F55.1 escoge Omnilingual,
# el indexador la inserta como una transmisión más.
transcribe_and_index_audio(
    index,
    Path("asamblea-zona-quechua-2026.flac"),
    video_id="asamblea-2026-qu",
    title="Asamblea de Zona 2026 — Ayacucho",
    language="qu",  # router resuelve a omniASR_CTC_300M + lang quy_Latn
    source_url="https://tv.jw.org/...",
)

# Búsqueda full-text después:
for hit in index.search("Jehová", language="quy_Latn"):
    print(hit["text"], hit["source_url"])
```

Si además quieres búsqueda cross-lingual (transmisión quechua, query
en español), pasa `translate_to="es"` y el transcript se traduce con
NLLB-200 (F54) antes de indexar, preservando referencias bíblicas:

```python
transcribe_and_index_audio(
    index, audio, video_id="...", language="qu", translate_to="es"
)
```

## Referencias

- Repo upstream: <https://github.com/facebookresearch/omnilingual-asr>
- Blog Meta AI: <https://ai.meta.com/blog/omnilingual-asr-advancing-automatic-speech-recognition/>
- Paper: arXiv 2511.09690
- Licencia: Apache 2.0 (código + pesos). Datos del corpus son CC-BY 4.0.
- Compatible con la licencia GPL-3.0 del toolkit como dependencia opcional.
