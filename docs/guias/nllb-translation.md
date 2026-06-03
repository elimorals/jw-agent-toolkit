# Guía — NLLB-200 translation con preservación de referencias (Fase 54)

> Traducir texto entre **200 idiomas** vía NLLB-200 (Meta) corriendo
> localmente con CTranslate2 INT8, **preservando exactamente las
> referencias bíblicas**. La función `translate_preserving_references()`
> garantiza que ningún LLM/encoder-decoder altere "Juan 3:16" durante la
> traducción.

## Por qué un proveedor especializado

| Capacidad | LLM general (GPT/Claude) | **NLLB-200** |
|---|---|---|
| Idiomas | ~50 con calidad uniforme | 200 con FLORES-200 supervision |
| Calidad en low-resource | inconsistente, **alucina** | encoder-decoder dedicado |
| Costo por carácter | API tokens | local, 0 ¢ |
| Determinismo | temperatura > 0 | deterministico por defecto |
| Latencia | 100ms-segundos | sub-segundo en M-series con INT8 |
| Hardware | ninguno (cloud) | 3.5–7 GB RAM/VRAM |
| Privacidad | datos al cloud | 100% local |
| **Licencia** | comercial OK | **CC-BY-NC-4.0** |

Para textos de jw.org cuya traducción no debe alucinar (versículos,
nombres propios, fechas de asamblea), NLLB es la opción
**determinística y barata**.

## License-as-attribute

`NLLBProvider.is_commercial_safe = False` (atributo del provider). El
router F55.1 lo respeta:

```python
from jw_core.translation_providers import get_translation_provider

# Uso individual / congregación → todo OK.
prov = get_translation_provider(source="es", target="en")
# → NLLBProvider

# Deployment comercial → NLLB filtrado.
prov = get_translation_provider(source="es", target="en", commercial=True)
# → raises TranslationError("No translation provider available...")
```

Esto vuelve la política de licencia **chequeable a runtime**, no
narrativa. Cualquier futuro provider commercial-safe (DeepL, GPT-5,
Claude) entra al router con `is_commercial_safe = True` y el `commercial=True`
del caller los selecciona automáticamente.

## Bootstrap

```bash
uv add 'jw-core[translation-nllb]'
```

El extra instala:

- `ctranslate2 >= 4.7.0` — runtime de inferencia INT8. **Tiene wheels
  cp313**, así que NLLB vive en proceso del toolkit (no necesita venv
  aparte, a diferencia de Omnilingual F53).
- `transformers >= 4.45.0` — sólo para el tokenizer SentencePiece de
  NLLB; el modelo en sí lo carga ctranslate2.
- `sentencepiece >= 0.2.0` — backend del tokenizer.
- `huggingface_hub >= 0.24.0` — descarga del modelo CT2 desde HF.

### Descarga del modelo

Primera transcripción descarga `OpenNMT/nllb-200-3.3B-ct2-int8` (~7 GB)
a `~/.jw-core/nllb/`. Override con:

```bash
export JW_NLLB_MODEL=OpenNMT/nllb-200-1.3B-ct2-int8  # más liviano, ~3.5 GB
export JW_NLLB_MODEL_DIR=/mnt/llm-models/nllb-3.3b
```

## Uso

### Vía CLI

```bash
jw translate "Como dice Juan 3:16, Dios amó al mundo." --from es --to en
# ⚠ Using nllb-200 (CC-BY-NC; non-commercial only).
# As John 3:16 says, God loved the world.
```

`Juan 3:16` → `John 3:16` automáticamente porque el sistema **enmascara
la referencia antes de pasarla al modelo**, restaurándola en el idioma
destino al final.

Flags:
- `--from`/`-s`: ISO-639-1 (`es`) o FLORES (`spa_Latn`).
- `--to`/`-t`: igual.
- `--commercial`: salta NLLB; falla si no hay otro provider disponible.
- `--provider`/`-p`: forzar `nllb-200` (explicit).

### Vía Python

#### API alta: traducir preservando refs

```python
from jw_core.translation import translate_preserving_references
from jw_core.translation_providers import get_translation_provider

provider = get_translation_provider(source="es", target="en")

text = "Como dice Juan 3:16, Dios amó al mundo. Léase Génesis 1:1."
translated = translate_preserving_references(
    text, source="es", target="en", provider=provider
)
print(translated)
# As John 3:16 says, God loved the world. Read Genesis 1:1.
```

#### API baja: provider directo (sin mask de refs)

```python
from jw_core.translation_providers.nllb import NLLBProvider

provider = NLLBProvider()
raw = provider.translate("Hola mundo.", source="es", target="en")
# "Hello world."
```

Úsalo solo cuando estás seguro de que no hay refs bíblicas en el input.

### Vía MCP

```
mcp.tools.translate_preserving_refs(
    text="Como dice Juan 3:16, Dios amó al mundo.",
    source="es",
    target="en",
)
# Returns:
# {
#   "text": "As John 3:16 says, God loved the world.",
#   "source": "es",
#   "target": "en",
#   "provider": "nllb-200",
#   "commercial_safe": false,
# }
```

## Cómo funciona ref-preservation

Tres pasos secuenciales:

```
INPUT  : "Como dice Juan 3:16, Dios amó al mundo."
                       │
                       │  mask_references()  (jw_core.translation)
                       ▼
MASKED : "Como dice <<REF:0>>, Dios amó al mundo."
   refs : [{book_num:43, chapter:3, verse_start:16,
            verse_end:None, language:"es"}]
                       │
                       │  provider.translate(masked, src, tgt)
                       │  (model only sees opaque tokens)
                       ▼
TRANS. : "As <<REF:0>> says, God loved the world."
                       │
                       │  restore_references(translated, refs, target_language="en")
                       ▼
OUTPUT : "As John 3:16 says, God loved the world."
```

Garantías:

- **El modelo nunca ve la referencia.** No puede alucinar el versículo.
- **El render del nombre del libro usa la tabla `BOOKS`** de `jw_core.data`,
  con prioridad por idioma destino. "Juan" se vuelve "John" en `en`,
  "João" en `pt`, "Иоанн" en `ru`.
- **Soporta rangos** (`Juan 3:16-18` → `John 3:16-18`).

## Modelos disponibles vía CTranslate2 (HuggingFace)

| Repo HF | Tamaño | RAM | Calidad FLORES BLEU |
|---|---|---|---|
| `OpenNMT/nllb-200-3.3B-ct2-int8` *(default)* | 3.3B | ~7 GB | mejor |
| `OpenNMT/nllb-200-1.3B-ct2-int8` | 1.3B | ~3.5 GB | buena |
| `OpenNMT/nllb-200-distilled-600M-ct2-int8` | 600M | ~1.5 GB | aceptable |
| `michaelfeil/ct2fast-nllb-200-3.3B` | 3.3B | ~7 GB | mejor (variante de OpenNMT) |

## Composición con otras fases

### F55.7 — cross-lingual research

`jw_agents.cross_lingual_research` usa NLLB en ambas direcciones:

```python
import asyncio
from jw_agents.cross_lingual_research import cross_lingual_research

# Query en español sobre artículos en inglés
result = asyncio.run(cross_lingual_research(
    "día de Jehová",
    user_language="es",
    corpus_language="E",       # MEPS para research_topic
    corpus_language_iso="en",  # ISO para NLLB
))

for finding in result.findings:
    print(finding.summary)      # traducido a español, refs en español
    print(finding.citation.url) # URL intacta (no se traduce)
```

### F55.8 — broadcasting cross-lingual

`audio/broadcasting.transcribe_and_index_audio(..., translate_to="en")`:
transcribe en idioma A vía Omnilingual, traduce a B vía NLLB con
ref-preservation, indexa en B.

## Limitaciones reconocidas

- **No es para textos muy largos.** NLLB encoder-decoder está optimizado
  para oraciones (<=512 tokens). Para Atalayas enteras, segmenta por
  párrafo (`text.split("\n\n")`) y traduce en batch.
- **Idiomas con sistemas de escritura sin tokenizer SentencePiece
  entrenado** pueden dar resultados pobres. Verifica BLEU FLORES de
  tu par antes de producir.
- **Style es periodístico moderno.** Para texto poético/devocional, un
  LLM general con un prompt afinado puede dar resultados más
  naturales (a costo de la determinismo y el riesgo de alucinación
  numérica que NLLB elimina).

## Referencias

- Modelo HF (original Meta): <https://huggingface.co/facebook/nllb-200-3.3B>
- Variante CT2 INT8: <https://huggingface.co/OpenNMT/nllb-200-3.3B-ct2-int8>
- Paper: arXiv 2207.04672 ("No Language Left Behind")
- Licencia: CC-BY-NC-4.0 (modelo + pesos). Datos del corpus FLORES-200 son
  CC-BY-SA-4.0.
- Atributos de licencia visibles en runtime: `provider.is_commercial_safe`.
