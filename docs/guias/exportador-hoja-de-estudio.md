# Exportador de hoja de estudio (PDF / DOCX / Anki / Markdown)

> Fase 31 — convierte cualquier `AgentResult` en un entregable imprimible o
> un mazo Anki de repaso espaciado. Markdown siempre disponible; los demás
> formatos son opt-in vía extras.

## Instalación

```bash
# baseline (markdown siempre)
uv sync --all-packages

# con extras opcionales
uv pip install 'jw-core[pdf]'    # WeasyPrint
uv pip install 'jw-core[docx]'   # python-docx
uv pip install 'jw-core[anki]'   # genanki
```

WeasyPrint requiere librerías nativas (cairo, pango). Ver
<https://doc.courtbouillon.org/weasyprint/stable/first_steps.html> para
instrucciones por plataforma.

## Uso (CLI)

```bash
# 1) Generar el AgentResult
uv run jw apologetics "Trinidad" --json > /tmp/trinity.json

# 2) Convertir
uv run jw export /tmp/trinity.json --format markdown --out hoja.md
uv run jw export /tmp/trinity.json --format pdf --out hoja.pdf --theme study-sheet
uv run jw export /tmp/trinity.json --format docx --out hoja.docx
uv run jw export /tmp/trinity.json --format apkg --out mazo.apkg --per-citation-cards
```

Pipeline en una sola línea:

```bash
uv run jw apologetics "Trinidad" --json | uv run jw export - -f pdf -o /tmp/x.pdf
```

## Estilos de cita

- `--citation-style inline-paren` — citas entre paréntesis dentro del cuerpo.
- `--citation-style footnote` (default) — marcadores `[^1]` con definiciones al final.
- `--citation-style bibliography` — cuerpo limpio + lista de fuentes al final.

## Plantillas personalizadas

Coloca un Jinja2 con el mismo nombre que un template built-in en
`~/.jw-agent-toolkit/templates/` para sobrescribirlo:

```
~/.jw-agent-toolkit/templates/study-sheet.html.j2
```

El resolver siempre prefiere la versión del usuario.

## Anki — re-export idempotente

El GUID de cada tarjeta deriva de `sha256(title + heading + body[:200])`.
Re-exportar el mismo `AgentResult` y reimportar el `.apkg` en Anki:
**actualiza** las notas existentes, no duplica.

## MCP

```json
{
  "tool": "export_study_sheet",
  "arguments": {
    "agent_result": { ... },
    "format": "pdf",
    "out_path": "~/Documents/hoja.pdf",
    "theme": "study-sheet",
    "citation_style": "footnote"
  }
}
```

Devuelve `{"out": "...", "format": "...", "bytes_written": N}` o `{"error": "..."}`.

## Diseño

Una IR única (`StudySheet`) intermedia. Cuatro exporters consumen la IR; nunca un
`AgentResult` directamente. Las dependencias pesadas se importan lazy, así que
importar `jw_core.exporters` nunca falla aunque falten los extras.
