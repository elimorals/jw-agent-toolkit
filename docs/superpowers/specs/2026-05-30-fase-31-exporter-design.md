# Fase 31 — Exportador de hoja de estudio (PDF / DOCX / Anki / Markdown)

> **Fecha**: 2026-05-30
> **Estado**: Diseño aprobado (pendiente de implementación)
> **Owner**: Elias
> **Tier**: 4 (capas de UX / nicho)
> **Tamaño**: M (~3-4 días)
> **Depende de**: ninguna fase bloqueante. Reutiliza `AgentResult` (todas las fases) y patrón SM-2 (Fase 14).
> **Documento padre**: [`2026-05-30-fases-22-32-overview.md`](2026-05-30-fases-22-32-overview.md)

## Motivación

Las 13 fases anteriores producen `AgentResult` con findings + citas verificables, pero el consumidor final muchas veces necesita un **artefacto entregable** (imprimible / repasable) en lugar del JSON:

- Una hoja de estudio en PDF para llevar a la reunión sin pantallas.
- Un DOCX para editar manualmente antes de imprimir o enviar.
- Un mazo Anki (`.apkg`) para repaso espaciado de las conclusiones doctrinales.
- Markdown para Obsidian / publicar / pegar en Notion.

Sin Fase 31, cada usuario re-implementa esta conversión en su flujo. Con Fase 31 cualquier `AgentResult` (apologetics, verse_explainer, research_topic, study_conductor, life_topics…) se convierte en uno de los cuatro formatos con una sola CLI o llamada MCP.

## Objetivos (en orden de prioridad)

1. **IR única**: una sola conversión `AgentResult → StudySheet`. Todos los exporters consumen `StudySheet`, nunca `AgentResult` directamente.
2. **Markdown siempre disponible**: sin extras, sin red, determinista — es la baseline mínima.
3. **PDF / DOCX / Anki opt-in** vía `[pdf]`/`[docx]`/`[anki]` extras. Cero hard dependency pesada.
4. **Citas verificables preservadas**: cada cita conserva URL + título + tipo. Tres modos de render: paréntesis inline, footnote, bibliografía.
5. **Plantillas pluggables**: el usuario puede sobrescribir Jinja2 en `~/.jw-agent-toolkit/templates/`.
6. **Anki idempotente**: re-export del mismo `StudySheet` actualiza el note existente (mismo `guid`), no duplica.

## No-objetivos (boundaries vinculantes)

- **No** generamos LLM prose nueva. El exporter solo formatea lo que ya viene en `findings[].summary` y `findings[].excerpt`.
- **No** descargamos imágenes de wol.jw.org. PDF/DOCX son texto + tipografía + estructura, no media.
- **No** firmamos PDFs ni añadimos DRM.
- **No** exportamos a EPUB / Kindle / HTML standalone (queda fuera de scope; PDF cubre imprimible).
- **No** subimos el `.apkg` a AnkiWeb. Generamos el archivo; el usuario lo importa.
- **No** modificamos `AgentResult` ni `Finding` — Fase 31 es solo lectura.

## Arquitectura

Nuevo módulo `jw_core.exporters` (parte de `packages/jw-core`, no paquete propio). Razón: depende solo de Pydantic + Jinja2 + (opcionales). No justifica un workspace member adicional.

```
packages/jw-core/src/jw_core/exporters/
├── __init__.py
├── ir.py             # StudySheet (Pydantic) + from_agent_result()
├── markdown.py       # MarkdownExporter — siempre disponible
├── pdf.py            # PDFExporter — opt-in [pdf] (weasyprint + jinja2)
├── docx.py           # DocxExporter — opt-in [docx] (python-docx)
└── anki.py           # AnkiExporter — opt-in [anki] (genanki)

packages/jw-core/src/jw_core/templates/study_sheet/
├── plain.html.j2
└── study-sheet.html.j2
```

Y la integración:

```
packages/jw-cli/src/jw_cli/commands/export.py     # jw export <json> --format pdf
packages/jw-mcp/src/jw_mcp/server.py              # tool export_study_sheet(...)
```

### Reglas duras de diseño

1. **Una sola conversión** `AgentResult → StudySheet`. Cada exporter recibe `StudySheet`, **nunca** `AgentResult`. Razón: cada exporter solo decide cómo *renderizar*, no qué cosa renderizar.
2. **Imports lazy**: `weasyprint`, `python-docx`, `genanki` solo se importan dentro de la función de exporter. Importar `jw_core.exporters` sin extras nunca falla.
3. **Sin red en exporters**. Si un finding lleva una URL, se cita; no se descarga.
4. **Cada exporter expone exactamente una función pública**: `export_<format>(sheet, *, out, options) -> Path`.
5. **Plantillas resueltas vía `_resolve_template(name)`**: primero `~/.jw-agent-toolkit/templates/<name>`, luego `jw_core.templates.study_sheet.<name>` empaquetado.

## La IR — `StudySheet`

```python
# packages/jw-core/src/jw_core/exporters/ir.py

from pydantic import BaseModel, Field
from typing import Literal, Any

CitationStyle = Literal["inline-paren", "footnote", "bibliography"]

class CitationIR(BaseModel):
    """Cita normalizada para todos los exporters."""
    url: str
    title: str = ""
    kind: str = ""              # 'verse' | 'article' | 'daily_text' | 'chapter'
    short_label: str = ""       # 'Juan 3:16' o 'w24/05 art.18'
    metadata: dict[str, Any] = Field(default_factory=dict)

class StudySection(BaseModel):
    """Una sección de la hoja: heading + body + citas."""
    heading: str
    body: str                   # texto plano (markdown opcional en exporters)
    excerpt: str = ""           # cita literal del original (opcional)
    citations: list[CitationIR] = Field(default_factory=list)

class StudySheet(BaseModel):
    """Documento intermedio. Todos los exporters lo consumen."""
    title: str
    subtitle: str = ""
    language: str = "es"        # 'en' | 'es' | 'pt'
    sections: list[StudySection] = Field(default_factory=list)
    footer_note: str = ""       # ej. "Generado por jw-agent-toolkit"
    metadata: dict[str, Any] = Field(default_factory=dict)

    @classmethod
    def from_agent_result(
        cls,
        result: "AgentResult | dict",
        *,
        title: str | None = None,
        language: str = "es",
        include_citations: bool = True,
    ) -> "StudySheet":
        """Único punto de conversión AgentResult → StudySheet."""
        ...
```

### Reglas de conversión `AgentResult → StudySheet`

1. `title` = `title` arg si se da, si no `result.metadata.get("title")` si existe, si no `result.query` truncado a 80 chars.
2. `subtitle` = `result.agent_name` formateado humano (`apologetics → "Análisis apologético"`).
3. Cada `Finding` → un `StudySection`:
   - `heading` = `finding.summary` (primera línea truncada a 100 chars).
   - `body` = `finding.summary` completo.
   - `excerpt` = `finding.excerpt` si existe.
   - `citations` = `[finding.citation]` mapeado a `CitationIR` (si `include_citations`).
4. `result.warnings` no entra como sección; va al `footer_note` con prefijo "Advertencias:".
5. Si el `AgentResult` tiene 0 findings → `StudySheet` con 1 sección "(sin resultados)".

## Los cuatro exporters

### 1. Markdown — siempre disponible

`export_markdown(sheet, *, out, citation_style="footnote") -> Path`.

- Render determinista, sin dependencias externas.
- Tres estilos:
  - **inline-paren**: `…texto del cuerpo (Juan 3:16, wol.jw.org/...).`
  - **footnote**: `…texto del cuerpo[^1].` + footnotes al final.
  - **bibliography**: cuerpo limpio + lista numerada de fuentes al final.
- Cabecera incluye `# title` + `## subtitle` + `_idioma_`.
- Cada sección es `## heading` + cuerpo + (opcional) excerpt como blockquote.

### 2. PDF — opt-in `[pdf]`

`export_pdf(sheet, *, out, theme="study-sheet", citation_style="footnote") -> Path`.

- Implementación: Jinja2 renderiza `templates/study_sheet/<theme>.html.j2` → WeasyPrint convierte HTML a PDF.
- Dos temas built-in:
  - `plain`: tipografía limpia (Inter / system serif), márgenes amplios.
  - `study-sheet`: estilo cuaderno de estudio (Charter / Source Serif Pro, número de línea opcional, espacio para notas a la derecha).
- Citas con `citation_style`:
  - `inline-paren`: `<sup>(<a href="…">Juan 3:16</a>)</sup>` inline.
  - `footnote`: numeradas, lista al final de cada sección o del documento.
  - `bibliography`: bibliografía global al final del PDF.
- WeasyPrint debe estar instalada como extra; el módulo levanta `MissingDependencyError` con instrucción `pip install jw-core[pdf]` si no está.

### 3. DOCX — opt-in `[docx]`

`export_docx(sheet, *, out, citation_style="footnote") -> Path`.

- Usa `python-docx` directamente (no template Jinja2 — DOCX usa estructura programática).
- Headings → `Heading 1` (title) / `Heading 2` (section.heading) / `Normal` (body).
- Excerpt → `Intense Quote` style.
- Footnotes vía `python-docx` API (footnote endpoint).
- Hyperlinks de citas insertadas como `add_hyperlink(...)` helper.

### 4. Anki — opt-in `[anki]`

`export_apkg(sheet, *, out, deck_name=None, per_citation_cards=False) -> Path`.

- Implementación: `genanki.Deck` + `genanki.Note` + `genanki.Package`.
- Una nota por sección por defecto:
  - **Front**: `section.heading`.
  - **Back**: `section.body` + excerpt + lista de citas con URL clickable.
- Si `per_citation_cards=True` y la sección tiene >1 cita: una nota extra por cita (front = `citation.short_label`, back = `section.heading` + URL).
- **GUID estable**: `sha256(sheet.title + section.heading + section.body[:200])`. Re-export = update, no duplicate.
- `deck_name` default = `sheet.title`. `model_id` y `deck_id` derivados con `sha256` del title (estables entre re-runs).

### Resolución de plantillas

```python
# en pdf.py
def _resolve_template(name: str) -> Path:
    user_dir = Path.home() / ".jw-agent-toolkit" / "templates"
    user_path = user_dir / name
    if user_path.exists():
        return user_path
    return Path(__file__).parent.parent / "templates" / "study_sheet" / name
```

Esto cumple el principio de "plantillas pluggables sin tocar código del paquete".

## Modelo de errores

Una excepción única en `jw_core.exporters`:

```python
class ExportError(Exception): ...
class MissingDependencyError(ExportError):
    """Se levanta cuando un extra opcional (weasyprint/python-docx/genanki) no está instalado."""
```

Cada exporter detecta su dep al inicio:

```python
def export_pdf(...):
    try:
        import weasyprint
    except ImportError as e:
        raise MissingDependencyError(
            "pip install 'jw-core[pdf]' to enable PDF export"
        ) from e
    ...
```

## Integración

### CLI (`jw-cli`)

```
jw export RESULT.json --format pdf --out hoja.pdf
jw export RESULT.json --format docx --out hoja.docx --citation-style bibliography
jw export RESULT.json --format apkg --out estudio.apkg --per-citation-cards
jw export RESULT.json --format markdown --out hoja.md --title "Trinidad — análisis"
```

`RESULT.json` es el `AgentResult.to_dict()` serializado. El CLI también acepta `--from-stdin` para pipelinear.

### MCP (`jw-mcp`)

Nueva herramienta:

```python
@app.tool()
def export_study_sheet(
    agent_result: dict,
    format: Literal["markdown", "pdf", "docx", "apkg"],
    out_path: str,
    title: str | None = None,
    citation_style: Literal["inline-paren", "footnote", "bibliography"] = "footnote",
    include_citations: bool = True,
    theme: str = "study-sheet",
    per_citation_cards: bool = False,
) -> dict:
    """Convierte un AgentResult en hoja de estudio (md/pdf/docx/apkg)."""
```

Retorna `{"out": str, "format": str, "bytes_written": int}` o `{"error": "..."}`.

## Casos de uso reales

1. **Hermano que quiere estudiar Trinidad este sábado**: ejecuta `jw apologetics "Trinidad" > result.json && jw export result.json --format pdf` → PDF impreso.
2. **Precursora que quiere repasar pasajes apologéticos**: `jw research-topic "alma humana" > result.json && jw export result.json --format apkg --per-citation-cards` → mazo Anki para repaso diario.
3. **Anciano preparando discurso público**: `jw meeting-helper "Romans 12:1" > result.json && jw export result.json --format docx` → DOCX para añadir notas personales antes de imprimir.
4. **Investigador en Obsidian**: pipeline MCP que llama agente + `export_study_sheet(format="markdown")` y guarda en vault.

## Riesgos y mitigaciones

| # | Riesgo | Mitigación |
|---|---|---|
| 1 | WeasyPrint requiere libs nativas (cairo, pango) que no compilan en todas las plataformas | Documentado como opt-in `[pdf]`. Markdown siempre funciona como fallback. CI no instala `[pdf]` por defecto |
| 2 | `python-docx` produce un XML específico que algunas versiones de Word no abren correctamente | Generamos con docx ≥ 1.1 (Office Open XML estándar). Tests validan que el archivo es ZIP válido y contiene `word/document.xml` |
| 3 | `genanki` cambia el modelo de cards entre versiones — los GUIDs viejos podrían no migrar | Pin `genanki>=0.13,<1.0`. GUID strategy es nuestra, no de genanki |
| 4 | Citas con URLs largas rompen layout en PDF | CSS `word-wrap: break-word` en plantillas. Test visual manual con URL muy larga |
| 5 | Caracteres no latinos (chino/coreano para ediciones futuras) → fuentes default no cubren | Plantilla declara `unicode-range` y usa stack con Noto Sans CJK fallback. Si la fuente falta el PDF renderiza tofu — documentado |
| 6 | Anki re-export con cambios menores genera GUID nuevo y duplica | GUID solo depende del `heading + body[:200]`. Cambios mayores son intencionales (nuevo card); cambios menores (typo en cite) se sobrescriben mediante import update |
| 7 | Inyección HTML maliciosa via `finding.summary` → XSS en PDF/DOCX | Jinja2 con `autoescape=True` por defecto. python-docx no interpreta HTML. Markdown escape básico para `[`, `]`, `(`, `)` |
| 8 | Plantilla de usuario rota explota WeasyPrint | `_resolve_template` valida que el archivo existe y tiene extensión esperada. Errores Jinja2 se capturan y reempaquetan como `ExportError` con path y línea |

## Métricas de éxito

- `jw export result.json --format markdown` corre en <100ms para un `AgentResult` típico (5 findings).
- `jw export result.json --format pdf` corre en <3s.
- 1 ronda de import → revisar en Anki Desktop → re-export muestra "X notes updated, 0 added".
- Markdown output válido para CommonMark (lint con `markdownlint`).
- DOCX abre correctamente en Word 365, LibreOffice 7+, Google Docs.
- PDF pasa `pdfinfo` sin warnings.
- Documentado en `docs/guias/exportador-hoja-de-estudio.md`.
- Audit 1:1 en `docs/VISION_AUDIT.md` (sección #11 "Exportador").

## Pendientes explícitos (post-Fase 31)

- Exportar a EPUB / Kindle — fase futura si surge demanda.
- Exportar diapositivas (PPTX) — `pptx` skill ya existe; podría ser Fase 33.
- Templates de comunidad / theme marketplace.
- Re-importar `.apkg` → reconstruir `AgentResult` (round-trip). No es objetivo de Fase 31.

## Cómo verificar al cerrar

```bash
# 1. Instalar con todos los extras
uv sync --all-packages --all-extras

# 2. Generar un AgentResult de prueba
uv run jw apologetics "Trinidad" --json > /tmp/trinity.json

# 3. Markdown (siempre)
uv run jw export /tmp/trinity.json --format markdown --out /tmp/trinity.md

# 4. PDF (necesita [pdf])
uv run jw export /tmp/trinity.json --format pdf --out /tmp/trinity.pdf

# 5. DOCX (necesita [docx])
uv run jw export /tmp/trinity.json --format docx --out /tmp/trinity.docx

# 6. Anki (necesita [anki])
uv run jw export /tmp/trinity.json --format apkg --out /tmp/trinity.apkg

# 7. Tests del módulo
.venv/bin/python -m pytest packages/jw-core/tests/test_exporter_*.py -v
```

## Plan de implementación

Spec hijo: [`docs/superpowers/plans/2026-05-30-fase-31-exporter-plan.md`](../plans/2026-05-30-fase-31-exporter-plan.md).

Pasos cronológicos (resumidos — ver plan):

1. IR `StudySheet` + `from_agent_result` con tests.
2. Markdown exporter (3 estilos de cita) con tests.
3. Plantillas Jinja2 `plain` y `study-sheet`.
4. PDF exporter con WeasyPrint + skip-if-missing en tests.
5. DOCX exporter con python-docx + skip-if-missing.
6. Anki exporter con genanki + GUID estable + skip-if-missing.
7. Resolución de templates de usuario.
8. CLI `jw export`.
9. MCP tool `export_study_sheet`.
10. Guía + audit.

Cada paso con su PR + tests verdes + sin regresión.
