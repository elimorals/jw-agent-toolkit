---
title: "Wire-up multilingüe (Fase 55)"
description: "Los 8 call sites que convierten F50-F54 de islas portadas en capacidades del toolkit."
date: "2026-06-02"
---

# Guía — Wire-up multilingüe (Fase 55)

> Cómo el toolkit pasa de "tener los proveedores instalados" a "los usa
> automáticamente". Esta guía explica las 8 sub-fases de integración
> F55.1–F55.8 que conectan F50–F54 al resto del ecosistema.

## El gap "portar vs. integrar"

Fases 50–54 portaron código limpio: writers de JWPUB y .jwlibrary,
schemas organized-app en Pydantic, providers Omnilingual ASR y NLLB-200
translation. Cada uno con tests verdes.

**Pero ningún módulo del toolkit los invocaba.** Auditoría honesta: un
`grep -rn "models_organized\|NLLBProvider\|JwpubBuilder" --include="*.py" .`
fuera de `tests/` arrojaba cero coincidencias. Los módulos vivían como
islas.

F55 son los **call sites**: el factory de ASR aprende que existe
Omnilingual; el CLI gana `jw translate`; el MCP expone una tool nueva;
un agente compone NLLB con `research_topic`. Cada uno es pequeño (≤50
LOC), pero el efecto multiplicativo vuelve real la integración.

## F55.1 — Routers automáticos por idioma + licencia

### `get_asr_provider(language=...)`

```python
from jw_core.audio.transcription import get_asr_provider

# El router consulta `languages_supported` de cada proveedor:
#   DeepgramProvider.languages_supported  = {"en", "es", "pt", ...}  (~16)
#   WhisperTurboProvider.languages_supported = {}  (autodetect)
#   OmnilingualProvider.languages_supported = {}  (1672 via runtime check)

provider = get_asr_provider(language="en")  # → DeepgramProvider (si API key)
provider = get_asr_provider(language="qu")  # → OmnilingualProvider (catch-all)
provider = get_asr_provider()               # → primer disponible de DEFAULT_ASR_CHAIN
```

Resolución (en orden):

1. **Explicit `name`** o `JW_ASR_PROVIDER` env.
2. **Match por `language`**: el primer proveedor cuya
   `languages_supported` cubra el idioma.
3. **Fallback**: Omnilingual catch-all (cubre 1672).
4. **DEFAULT_ASR_CHAIN**: `["deepgram", "whisper-turbo", "omnilingual"]`.

### `get_translation_provider(commercial=...)`

```python
from jw_core.translation_providers import get_translation_provider

# Uso personal / congregación
prov = get_translation_provider(source="es", target="en")  # → NLLB

# Deployment comercial
prov = get_translation_provider(source="es", target="en", commercial=True)
# raises TranslationError("No translation provider available")
# (NLLB excluido por is_commercial_safe=False)
```

`commercial=True` filtra **estructuralmente** a NLLB CC-BY-NC. Cuando
añadas otro provider commercial-safe (DeepL, Claude, GPT-5) entrará al
chain con `is_commercial_safe=True` y el caller seguirá siendo idéntico.

### Por qué esto importa

Antes: agentes hardcodeaban `DeepgramProvider()` o `WhisperTurboProvider()`.
Tenían que saber **qué idioma cubre cada uno**. Cualquier audio en
quechua fallaba silenciosamente.

Ahora: un agente pasa `language="qu"` al factory y obtiene el mejor
provider disponible **sin saber nada de Omnilingual**. La capacidad
multilingüe se vuelve infraestructural, no incidental.

## F55.2 — `jw translate` CLI + MCP tool

### CLI

```bash
jw translate "Como dice Juan 3:16, Dios amó al mundo." \
    --from es \
    --to en
# ⚠ Using nllb-200 (CC-BY-NC; non-commercial only).
# As John 3:16 says, God loved the world.
```

Lee de stdin si no le pasas argumento (`echo "..." | jw translate -s es -t en`).

### MCP tool

```python
mcp.tools.translate_preserving_refs(
    text="Como dice Juan 3:16, Dios amó al mundo.",
    source="es",
    target="en",
)
# {"text": "As John 3:16 says, God loved the world.",
#  "source": "es", "target": "en",
#  "provider": "nllb-200", "commercial_safe": false}
```

### Refactor del MCP existente

`mcp.tools.transcribe_audio` antes hardcodeaba el provider con
`provider="whisper_turbo"`. F55.2 lo refactoriza para usar
`get_asr_provider(provider_arg, language=language_arg)`. Mismo nombre
de tool, comportamiento auto-routing.

## F55.3 — `jw library` CLI

`jw library inspect`, `re-export`, `from-notes` exponen los writers de
F52 como comandos. Caso de uso clave: agentes que escriben notas JSON
producen `.jwlibrary` instalables en la app oficial.

Ver guía dedicada: [`jwlibrary-writer.md`](jwlibrary-writer.md).

## F55.4 — `jw jwpub build` CLI

`jw jwpub` se convirtió en sub-app. El comando `jw jwpub <path>`
anterior ahora es `jw jwpub inspect <path>` — backward-compat
ligeramente rota a cambio de `jw jwpub build <folder>` que empaqueta
HTML+media como `.jwpub` vía el writer F50.

Ver guía dedicada: [`jwpub-writer.md`](jwpub-writer.md).

## F55.5 — IO de backup organized-app

```python
from jw_core.integrations.organized_app import (
    parse_organized_backup,
    write_organized_backup,
)

# Leer un backup producido por la PWA
backup = parse_organized_backup("backup-2026-06-01.json")
print(len(backup.persons))                    # 87
print(backup.schedules[0].weekOf)             # "2026-06-01"
print(backup.user_field_service_reports[0]
      .report_data.bible_studies.monthly)     # 3

# Escribir un backup
write_organized_backup("export.json", backup)
```

El formato JSON usa **dict indexado por UID** para algunos colecciones
(`persons[uid] = PersonType`) y **arrays** para otros
(`meeting_attendance: [...]`). El parser normaliza ambos a listas
Python; el writer reconstruye los dict indexed shapes que la PWA espera.

### Pipeline cross-toolkit

```
organized-app PWA  ─── export backup ───►  toolkit (read)
toolkit (read)     ─── agentes/scripts ─►  modificación
toolkit (write)    ─── export backup ───►  organized-app PWA (import)
```

El toolkit pasa a ser un **backend headless** sobre los mismos datos
que la PWA. Casos: notificaciones programáticas, validación de
asignaciones, dashboards de servicio, sync con sistema de tickets
internos.

## F55.6 — Bridge MonthlyReport ↔ S-21

`jw_core.ministry.field_report.MonthlyReport` (aggregate local del
toolkit) ↔ `UserFieldServiceMonthlyReportType` (formato organized-app
post-2023).

```python
from jw_core.ministry.organized_bridge import (
    to_organized_monthly_report,
    from_organized_monthly_report,
)

# Tu store SQLite local agregó las horas y studies
local_report = field_store.monthly_summary("2026-06")

# Convertir al formato que organized-app espera
organized = to_organized_monthly_report(
    local_report,
    person_uid="me",
    pioneer=False,       # publisher común; horas no se reportan
    shared_ministry=True,
    status="pending",
)

# El agente lo añade al backup y se sincroniza al PWA
backup.user_field_service_reports.append(organized)
write_organized_backup("export.json", backup)
```

Reglas post-2023 S-21 implementadas:

- `pioneer=False` ⇒ `hours.field_service.monthly = "0"` (publishers no
  reportan horas).
- `pioneer=True` ⇒ horas como string (formato JW legacy, evita
  float drift).
- `bible_studies.monthly` viene del `active_studies_max` del aggregate
  local.

## F55.7 — Agente cross_lingual_research

El killer feature multilingüe. Compone NLLB con `research_topic`:

```python
import asyncio
from jw_agents.cross_lingual_research import cross_lingual_research

result = asyncio.run(cross_lingual_research(
    "día de Jehová",           # query en español
    user_language="es",
    corpus_language="E",       # MEPS, lo que research_topic acepta
    corpus_language_iso="en",  # ISO, lo que NLLB acepta
))

for finding in result.findings:
    print(finding.summary)           # traducido a español
    print(finding.excerpt)           # traducido a español
    print(finding.citation.url)      # URL inglesa intacta
```

### Flujo interno

```
"día de Jehová"   (es)
       │
       │ NLLB translate (es→en) preservando refs
       ▼
"day of Jehovah"  (en)
       │
       │ research_topic(query=en, language="E")
       │ ↓ CDN search jw.org
       │ ↓ WOL article fetch
       │ ↓ extract Findings (summary, excerpt en inglés)
       ▼
[ Finding{summary="...", excerpt="See John 3:16."},
  Finding{summary="...", excerpt="..."} ]
       │
       │ Por cada finding:
       │   NLLB translate (en→es) preservando refs
       │   summary, excerpt → español; citation.url intacto
       ▼
[ Finding{summary="...(es)", excerpt="Véase Juan 3:16."},
  ... ]
```

### Garantías

- **Las refs sobreviven ambas direcciones de traducción**. El modelo
  nunca ve `Juan 3:16` ni `John 3:16` — solo `<<REF:0>>`.
- **El URL nunca se traduce.** `https://wol.jw.org/en/...` queda igual.
- **El tracing (Fase 43) ve los tres pasos**: `translate_query`,
  `research_topic_steps`, `translate_findings`.

### Caso de uso real

Un publicador hispanohablante quiere investigar "Jeremías 25:32" en
profundidad. Las herramientas de búsqueda en jw.org **en español**
devuelven menos artículos que **en inglés** porque el corpus inglés es
2-3× más amplio. Con `cross_lingual_research`:

1. Pregunta en español: "Qué dice Jeremías 25:32 sobre el día de Jehová".
2. Toolkit traduce a inglés, busca en el corpus inglés, encuentra 15
   artículos relevantes.
3. Excerpts traducidos de vuelta a español. Referencias bíblicas
   renderizadas como "Jeremías" (no "Jeremiah").
4. Publicador estudia en su idioma con corpus completo.

## F55.8 — Broadcasting multilingüe

`audio/broadcasting.transcribe_and_index_audio` extiende el indexador
de transmisiones (Fase 7-8) para:

1. **Audio sin VTT preexistente**: la mayoría de transmisiones JW en
   idiomas minoritarios no se publican con subtítulos. El router F55.1
   selecciona Omnilingual automáticamente y transcribe.
2. **Indexar cross-lingual**: con `translate_to="en"`, el transcript
   se traduce con NLLB antes de guardarlo en el índice — una asamblea
   en quechua se vuelve searchable en inglés.

```python
from jw_core.audio.broadcasting import (
    BroadcastingIndex,
    transcribe_and_index_audio,
)

index = BroadcastingIndex()

# Asamblea de zona en Bolivia (Aymara)
transcribe_and_index_audio(
    index,
    "asamblea-aymara-2026.flac",
    video_id="asamblea-2026-ay",
    title="Asamblea de Zona 2026 — Bolivia",
    language="ay",          # → router escoge Omnilingual
    source_url="https://tv.jw.org/...",
    translate_to="es",      # transcript indexado en español
)

# Búsqueda full-text en español ahora encuentra contenido aymara
for hit in index.search("Jehová"):
    print(hit["language"], hit["text"][:80])
    # es  "[ayr_Latn->es] Jehová muy_pacha kachunchik..."
```

## Tests F55

24 tests nuevos atravesando los 8 wire-up paths:

- `test_provider_routing.py` (15): routers ASR + translation con
  mocks de `is_available`.
- `test_library_cli.py` (3): `jw library from-notes` end-to-end con
  parse round-trip; `inspect`; `re-export --script`.
- `test_jwpub_build_cli.py` (2): build folder → .jwpub → parse,
  empty-folder failure.
- `test_organized_backup_io.py` (6): parse indexed-by-uid + array,
  round-trip file, write reconstructs indexed shapes, skip malformed
  rows, invalid file raises.
- `test_organized_bridge.py` (5): pioneer/publisher hours rules,
  status override, shared_ministry, round-trip back to MonthlyReport.
- `test_cross_lingual_research.py` (3): translation calls en orden
  correcto con `_RecordingTranslator`, warnings propagation, excerpt
  vacío skip.
- `test_broadcasting_multilingual.py` (2): transcribe basic +
  transcribe con translate_to.

Total tras F55: **1887 tests passing** en jw-core/jw-agents/jw-cli, zero
regresión.

## Composiciones a explorar (post-F55)

- **F55.7 + F55.4**: cross-lingual research que empaqueta los findings
  como `.jwpub` en el idioma del usuario.
- **F55.3 + F55.6**: agente que genera notas S-21 mensuales auto-
  rellenadas y produce un `.jwlibrary` con tag personalizado.
- **F55.8 + F55.1**: pipeline cron de ingestar todas las transmisiones
  nuevas de tv.jw.org en idiomas minoritarios y normalizar a un idioma
  índice común.

## Crédito

Esta fase no porta código externo. Es trabajo de integración interno.
La arquitectura de provider routing está inspirada en el patrón ya
existente de `jw_core.audio.tts` (F34 audio-premium).
