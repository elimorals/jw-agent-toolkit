# Fase 29 — Compositor de carta / teléfono / carrito (`letter_composer`)

> **Fecha**: 2026-05-30
> **Estado**: Diseño (pendiente de implementación)
> **Owner**: Elias
> **Tier**: 4 (capa UX / nicho)
> **Tamaño**: M (~3-4 días)
> **Depende de**: ninguna fase de Tier 1-3; reutiliza `presentation_builder`, `conversation_assistant`, `topic_index`.
> **Mide con**: Fase 22 (al menos 1 caso L1 por modalidad).
> **Documento padre**: [`2026-05-30-fases-22-32-overview.md`](2026-05-30-fases-22-32-overview.md)

## Motivación

Hoy el toolkit cubre puerta-a-puerta (`conversation_assistant`, `presentation_builder`, `apologetics`), revisitas (`revisit_tracker`), partes V&M (Fase 26) y cargas asociadas al estudio bíblico. Quedan **tres modalidades de servicio del campo** sin asistencia estructurada:

1. **Carta** (witnessing by letter) — territorio inaccesible, hogares vacíos, predicación pública por correspondencia.
2. **Teléfono** (phone witnessing) — territorio telefónico, llamada a contactos previos.
3. **Carrito** (cart witnessing) — testimonio público con exhibidor en parada de bus, plaza, calle.

Cada una pide un guion distinto: tiempo limitado, registro distinto y el publicador necesita un punto de partida calibrado a su audiencia. Fase 29 entrega un agente `letter_composer` que produce **andamiajes estructurados** (no prosa final): el LLM cliente (Claude Desktop, fine-tuned) los envuelve en lenguaje natural.

## Objetivos (en orden de prioridad)

1. Producir un scaffold estructurado por modalidad — **carta / teléfono / carrito** — con secciones nombradas (`opener`, `bridge`, `scripture`, `closing`) cada una con su `Finding` y citación verificable.
2. Adaptar el contenido a **6 audiencias** (default / new / religious / atheist / grieving / young / parents) × **8 familias temáticas** (familia/matrimonio, sufrimiento, esperanza, ciencia, paz, identidad, vicios, genérica) por kind.
3. Mantener **copyright-safe**: el scaffold solo cita la referencia bíblica + URL wol.jw.org. **Nunca** copia texto bíblico ni párrafos de publicaciones JW. La paráfrasis es del andamio en sí (texto neutro escrito por nosotros).
4. Cero red en tests (`topic` opcional, inyectable, mockeable).
5. Stateless por invocación — **ninguna PII se persiste**. `territory_hint` es solo decorativa, nunca filtra contenido.

## No-objetivos

- **No** sustituye al texto definitivo. El publicador escribe la carta final con su puño y letra; el guion telefónico lo lee con voz propia. Esto está documentado en la guía.
- **No** integra envío de cartas / SMS / llamadas (no es un servicio comunitario). Solo genera el contenido.
- **No** consulta CDN ni Topic Index a menos que se pase `topic` como dependencia. El uso normal es 100% local + plantillas.
- **No** almacena `territory_hint`, `audience`, `topic_or_question` ni resultados. Cualquier persistencia es responsabilidad del cliente (Obsidian, notas) y se hace fuera del agente.
- **No** aplica un límite estricto de palabras / segundos — entrega `time_target_seconds` y `word_count_target` como **metadata informativa**.

## Arquitectura

Tres módulos de datos en `jw-core` + un agente en `jw-agents` + un comando CLI + una tool MCP.

```
packages/jw-core/src/jw_core/data/
├── letter_templates.py         # plantillas carta (kind=letter)
├── phone_templates.py          # plantillas teléfono (kind=phone)
└── cart_templates.py           # plantillas carrito (kind=cart)

packages/jw-agents/src/jw_agents/
└── letter_composer.py          # orquesta plantilla × audiencia × familia

packages/jw-cli/src/jw_cli/commands/
└── letter.py                   # `jw letter --kind=letter --topic="esperanza" ...`

packages/jw-mcp/src/jw_mcp/server.py  (modificado)
  └─ register tool `compose_witnessing`
```

### Contratos

```python
# jw_agents.letter_composer
async def letter_composer(
    kind: Literal["letter", "phone", "cart"],
    *,
    language: str = "es",
    topic_or_question: str,
    audience: Literal[
        "default", "new", "religious", "atheist",
        "grieving", "young", "parents",
    ] = "default",
    territory_hint: str | None = None,   # cosmetic, e.g. "Lima, Perú"
    jw_link: str | None = None,          # explicit override; otherwise we suggest one
    topic: TopicIndexClient | None = None,  # optional, for `_topic_index` enrichment
) -> AgentResult
```

`AgentResult.findings` siempre tendrá **al menos 4** elementos, en este orden:

| # | `metadata.section` | `metadata.source`     | citation                   |
|---|--------------------|-----------------------|----------------------------|
| 1 | `opener`           | `letter_template`     | scaffold URL (`https://www.jw.org/`) |
| 2 | `bridge`           | `letter_template`     | scaffold URL               |
| 3 | `scripture`        | `verse_text`          | `BibleRef.wol_url(lang)`   |
| 4 | `closing`          | `letter_template`     | scaffold URL               |

Si se pasa `topic` (`TopicIndexClient`), se añade un 5º `Finding` con `metadata.section="topic_anchor"`, `metadata.source="topic_index"`.

`metadata` global:
- `kind`
- `audience`
- `topic_family` (resuelto)
- `language`
- `word_count_target` (carta: 150, teléfono: 0 — no aplica, carrito: 0)
- `time_target_seconds` (teléfono: 75, carrito: 30, carta: 0)
- `territory_hint`
- `jw_link_suggested`

### Resolución de `topic_family`

`topic_or_question` puede ser una palabra clave o una pregunta. Lo mapeamos con un diccionario heurístico por idioma:

```python
TOPIC_FAMILY_KEYWORDS = {
    "es": {
        "family":      ["familia", "matrimonio", "esposo", "esposa", "hijos", "padres"],
        "suffering":   ["sufrimiento", "dolor", "duelo", "muerte", "enfermedad"],
        "hope":        ["esperanza", "futuro", "paraíso", "reino", "resurrección"],
        "science":     ["ciencia", "evolución", "creación", "universo", "diseño"],
        "peace":       ["paz", "guerra", "ansiedad", "estrés", "tranquilidad"],
        "identity":    ["identidad", "propósito", "vida", "sentido"],
        "addictions":  ["adicción", "vicio", "alcohol", "drogas", "tabaco"],
    },
    "en": { ... },
    "pt": { ... },
}
```

Sin match → `topic_family = "generic"`. La función `resolve_topic_family(text, language)` es pura, determinista y se testea aislada.

### Lookup de plantilla

Cada módulo `*_templates.py` exporta:

```python
TEMPLATES: dict[tuple[str, str], LetterTemplate] = {
    # (audience, topic_family) -> LetterTemplate
}

def get_template(audience: str, topic_family: str) -> LetterTemplate:
    """Fallback (audience, family) → (audience, 'generic') → ('default', 'generic')."""
```

`LetterTemplate` es un `dataclass(frozen=True)`:

```python
@dataclass(frozen=True)
class LetterTemplate:
    opener: dict[str, str]        # {"en": "...", "es": "...", "pt": "..."}
    bridge: dict[str, str]
    closing: dict[str, str]
    suggested_scripture: str      # canonical reference e.g. "Revelation 21:4"
    suggested_jw_link: str        # canonical jw.org link
    time_target_seconds: int      # 0 if not applicable
    word_count_target: int        # 0 if not applicable
```

### Política de copyright (decisión explícita)

- El scaffold **paraphrasea con prosa neutra escrita por nosotros**. Los placeholders son del autor (Elias), no copiados de jw.org.
- Para el versículo, el `Finding.excerpt` queda **vacío** — solo `citation.url` + `citation.title` (referencia). El LLM cliente decide si abre la URL y cita el texto, y eso es problema suyo (ya gestionado por `verse_explainer` con su política propia).
- Para enlaces a jw.org el agente **sugiere** una URL canónica del Topic Index (cuando `topic` se pasa) o una URL genérica del tema (cuando no).
- Ningún territorio físico se asume "asignado" al usuario; `territory_hint` es solo decorativa.

## Idiomas

`en` / `es` / `pt`. Sin match → fallback a `en` con `warnings`.

## Diagrama de flujo

```
   topic_or_question ─► resolve_topic_family(...) ─► topic_family
                                                          │
                                                          ▼
   (audience, topic_family) ─► get_template(...) ─► LetterTemplate
                                                          │
                          ┌───────────┬──────────────────┼───────────────────┐
                          ▼           ▼                  ▼                   ▼
                       Opener      Bridge          Scripture           Closing
                          │           │                  │                   │
                          └───────────┴─────────► AgentResult.findings ◄─────┘
                                                          │
                                          if topic is not None:
                                                  ▼
                                           Topic anchor (TopicIndexClient)
```

## Modelos / interfaces (firmas)

```python
# jw_core.data.letter_templates
@dataclass(frozen=True)
class LetterTemplate:
    opener: dict[str, str]
    bridge: dict[str, str]
    closing: dict[str, str]
    suggested_scripture: str
    suggested_jw_link: str
    time_target_seconds: int = 0
    word_count_target: int = 150

TEMPLATES: dict[tuple[str, str], LetterTemplate]

def get_template(audience: str, topic_family: str) -> LetterTemplate: ...
def resolve_topic_family(text: str, language: str) -> str: ...
def list_audiences() -> list[str]: ...
def list_topic_families() -> list[str]: ...
```

Lo mismo para `phone_templates.py` (con `time_target_seconds=75`, `word_count_target=0`) y `cart_templates.py` (`time_target_seconds=30`, `word_count_target=0`).

```python
# jw_agents.letter_composer
async def letter_composer(
    kind: Literal["letter", "phone", "cart"],
    *,
    language: str = "es",
    topic_or_question: str,
    audience: str = "default",
    territory_hint: str | None = None,
    jw_link: str | None = None,
    topic: TopicIndexClient | None = None,
) -> AgentResult: ...
```

## Integración

### CLI

```bash
jw letter --kind letter --topic "esperanza para una madre en duelo" \
          --audience grieving --lang es \
          --territory "Lima, Perú"
jw letter --kind phone  --topic "ansiedad" --audience default --lang es
jw letter --kind cart   --topic "matrimonio" --audience parents --lang en
```

Salida: tabla Rich con secciones, time/word targets y enlace sugerido.

### MCP

```python
@server.tool
async def compose_witnessing(
    kind: str,
    language: str = "es",
    topic: str = "",
    audience: str = "default",
    territory_hint: str | None = None,
    jw_link: str | None = None,
) -> dict[str, Any]:
    """Compose a witnessing scaffold (letter | phone | cart).

    Sections: opener · bridge · scripture · closing. Each carries a
    verifiable citation URL.
    """
```

Devuelve `AgentResult.to_dict()`.

### Tests

`packages/jw-agents/tests/test_letter_composer.py`:

- `test_compose_letter_returns_4_sections_in_order`
- `test_compose_phone_has_time_target_75s`
- `test_compose_cart_has_time_target_30s`
- `test_topic_family_resolves_via_keyword_map`
- `test_territory_hint_inserted_in_opener_only`
- `test_jw_link_override_wins_over_template_default`
- `test_audience_fallback_to_default_when_unknown`
- `test_topic_family_fallback_to_generic_when_no_match`
- `test_topic_client_optional_adds_topic_anchor`
- `test_unknown_language_warns_and_uses_english`

Plus property-based test for: no `Finding` ever emits empty `citation.url`.

`packages/jw-core/tests/test_letter_templates.py` (smoke):

- Cada `TEMPLATES` dict contiene al menos `(audience, "generic")` para las 7 audiencias.
- Cada `LetterTemplate` define las tres claves `en`/`es`/`pt`.
- `resolve_topic_family` es idempotente y case-insensitive.

### Eval (Fase 22)

Tres `GoldenCase` L1 nuevos (uno por kind):

```
fixtures/golden_qa/l1/letter_composer_letter_grieving_es.yaml
fixtures/golden_qa/l1/letter_composer_phone_default_es.yaml
fixtures/golden_qa/l1/letter_composer_cart_parents_en.yaml
```

Schema:

```yaml
id: l1_letter_composer_letter_grieving_es
agent: letter_composer
layer: l1
input:
  kind: letter
  language: es
  topic_or_question: "Una madre que perdió a su hijo"
  audience: grieving
expected:
  min_findings: 4
  must_have_source: verse_text
  must_have_citation: true
  forbidden_keywords_in_findings:
    - "Jehová te pide"
    - "deberías sentir"
```

## Riesgos y mitigaciones

| # | Riesgo | Mitigación |
|---|---|---|
| 1 | Una plantilla suena "pastoral" / aconseja sentimientos | Test L1 con `forbidden_keywords` ("deberías sentir", "Jehová te pide"). PR review obligatorio en `_templates.py`. |
| 2 | Copyright al copiar prosa de jw.org | Política explícita: prose en plantillas escrita por Elias; `excerpt` de scripture queda vacío. Code-review checklist en `docs/guias/compositor-de-predicacion.md`. |
| 3 | Territory hint usado para discriminar contenido | `territory_hint` solo se concatena dentro del opener. No es input de `get_template` ni de `resolve_topic_family`. Test específico. |
| 4 | Una audiencia ofende a la persona real | Audiencias documentadas como **sugerencias del publicador**, no etiquetas asignadas. La guía lo explicita. |
| 5 | Tiempo objetivo se confunde con regla de uso | Documentado como **dato informativo**. CLI lo muestra con prefijo `aprox.` |
| 6 | Diccionario `TOPIC_FAMILY_KEYWORDS` se queda corto | Cualquier match falla → `generic` (fallback elegante). Cobertura se mide con eval L1 (caso `generic`). |
| 7 | Falta de plantilla `(audience, family)` | Fallback en cadena: `(audience, family) → (audience, 'generic') → ('default', 'generic')`. Test cubre los 3 niveles. |
| 8 | PII en `territory_hint` (e.g. "Casa de Juan Pérez, calle X") | Documentado en la guía: usar solo ciudad/zona, no domicilio. El toolkit no inspecciona ni almacena el valor. |

## Métricas de éxito

- ✅ Tres modalidades operativas (`letter`, `phone`, `cart`) con ≥4 findings cada una.
- ✅ Las 7 audiencias × 3 kinds × 8 familias resuelven (con fallback elegante donde no haya plantilla específica).
- ✅ 1 caso L1 por kind en `jw-eval` pasando.
- ✅ Test suite total verde — sin regresión sobre los 551 anteriores.
- ✅ Documentado en `docs/guias/compositor-de-predicacion.md` con ejemplos en es/en/pt.
- ✅ Audit 1:1 en `docs/VISION_AUDIT.md` para feature #4.

## Cómo verificar al cerrar

```bash
# Tests del feature
.venv/bin/python -m pytest packages/jw-core/tests/test_letter_templates.py \
                          packages/jw-agents/tests/test_letter_composer.py -v

# Eval L1
uv run jw eval --layer 1 --filter agent=letter_composer

# CLI smoke
uv run jw letter --kind letter --topic "esperanza" --audience grieving --lang es
uv run jw letter --kind phone  --topic "ansiedad"  --audience default  --lang en
uv run jw letter --kind cart   --topic "familia"   --audience parents  --lang pt

# MCP tool
echo '{"kind":"phone","language":"es","topic":"paz"}' \
  | uv run jw-mcp call compose_witnessing -

# Sin regresiones
.venv/bin/python -m pytest
```

## Plan de implementación

Hijo: [`2026-05-30-fase-29-letter-composer-plan.md`](../plans/2026-05-30-fase-29-letter-composer-plan.md). 13 tareas TDD.

## Lo que NO está en este plan (post-Fase 29)

- Selector de plantilla por *evento* (campaña especial, conmemoración, asamblea). → Fase futura.
- Renderizado a PDF de carta lista para imprimir. → Cubierto por Fase 31 (exporter).
- Métricas de uso / telemetría del publicador. → Fase futura, opt-in estricto.
- Traducción automática de plantillas a idiomas adicionales (signed lang, mn, …). → Manual por ahora.
