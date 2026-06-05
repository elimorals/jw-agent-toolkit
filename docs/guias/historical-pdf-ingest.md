# Ingest de PDFs históricos y docs Office (Fase 62)

> Cómo añadir al RAG personal Atalayas/Awake escaneadas, libros JW pre-EPUB
> y documentos compartidos por hermanos (guiones de discursos, programas de
> circuito, hojas de asistencia).

## ¿Por qué dos loaders distintos?

| Loader                           | Cubre                                       | Backend       |
| -------------------------------- | ------------------------------------------- | ------------- |
| `jw_rag.loaders.pdf_marker`      | `.pdf` (incluye escaneos OCR)               | `marker-pdf`  |
| `jw_rag.loaders.docs_markitdown` | `.docx`, `.pptx`, `.xlsx`                   | `markitdown`  |

`markitdown` también lee `.pdf`, pero su layout-parser pierde estructura
en escaneos históricos JW. Para PDFs siempre usar `pdf_marker`.

## Instalación

Ambos extras son opt-in para mantener la instalación base ligera
(`marker-pdf` trae torch + transformers, ~2 GB):

```bash
# Solo PDF:
uv add 'jw-rag[pdf-marker]'

# Solo Office docs:
uv add 'jw-rag[doc-markitdown]'

# Los dos juntos:
uv add 'jw-rag[loaders-all]'
```

Si invocas el loader sin el extra instalado:

```text
ModuleNotFoundError: marker-pdf is not installed.
Run: uv add 'jw-rag[pdf-marker]'
```

## Uso desde la CLI

```bash
# PDF de Atalaya 1950 (escaneo personal del usuario)
jw rag ingest-pdf ~/Documents/atalaya_1950_marzo.pdf --language es

# Programa de circuito compartido por el superintendente
jw rag ingest-office ~/Documents/programa_circuito_2026.docx --language es

# Store custom (por default ./jw-rag-store)
jw rag ingest-pdf ./mi.pdf --store ~/.jw-agent-toolkit/rag --language en
```

Si el extra falta, el comando sale con código 3 y un hint:

```bash
$ jw rag ingest-office hoja.docx
markitdown is not installed. Run: uv add 'jw-rag[doc-markitdown]'
$ echo $?
3
```

## Uso desde Python

```python
from pathlib import Path
from jw_rag.embed import FakeEmbedder      # o el embedder real
from jw_rag.store import VectorStore
from jw_rag.loaders import ingest_pdf, ingest_office_doc

store = VectorStore(Path("./jw-rag-store"), FakeEmbedder())
store.load()

n_pdf  = ingest_pdf(store, Path("atalaya_1950.pdf"), language="es")
n_docx = ingest_office_doc(store, Path("circuito.docx"), language="es")

print(f"Indexed {n_pdf + n_docx} new chunks")
store.save()
```

## Uso desde el servidor MCP (Claude Desktop / Claude Code)

Las dos tools quedan disponibles automáticamente cuando el host MCP
se conecta a `jw-mcp`:

```jsonc
// Tool call desde el agente
{"name": "ingest_pdf",        "arguments": {"pdf_path": "/Users/x/a.pdf", "language": "es"}}
{"name": "ingest_office_doc", "arguments": {"doc_path": "/Users/x/b.docx", "language": "es"}}
```

Respuesta JSON:

```json
{
  "pdf_path": "/Users/x/a.pdf",
  "language": "es",
  "chunks_added": 47,
  "store_total": 12834
}
```

Si el extra opcional no está instalado en el venv del servidor, la
respuesta llega con `{"error": "..."}` — el agente la ve sin romper la
sesión.

## Detección automática "¿es contenido JW?"

`pdf_marker` busca firmas conocidas en el markdown extraído:

- `Watch Tower`, `The Watchtower`, `JW.ORG`
- `Atalaya`, `Awake!`, `Despertad!`
- `Kingdom Hall`, `Jehovah's Witnesses`, `Testigos de Jehová`

Si encuentra al menos una → `metadata.is_jw = True`. Permite queries
filtradas a posteriori:

```python
hits = store.hybrid_search("trinidad", top_k=20)
jw_only = [h for h in hits if h.chunk.metadata.get("is_jw")]
```

Importante: el loader **nunca bloquea** ingest si `is_jw` es `False` —
el RAG personal del usuario puede tener material no-JW (apuntes,
estudios externos, etc.) que también es legítimo indexar.

`docs_markitdown` no aplica la firma JW por simplicidad (los Office
docs son típicamente material producido por el propio hermano), pero
el caller puede pasar `custom_meta={"is_jw": True}` si quiere etiquetar
manualmente.

## Idempotencia

Re-ingest del mismo archivo (mismo `sha256`) es **no-op**: el loader
calcula el hash, deriva `source_id = "pdf:<hash8>"` o `"doc:<ext>:<hash8>"`,
consulta `store.has_source(source_id)` y devuelve `0` si ya estaba
indexado. Útil para:

- Re-procesar un corpus completo en CI sin duplicar chunks.
- Reescaneo del usuario (si el PDF cambia → hash cambia → re-indexa).
- Pipelines de ingesta cron que apuntan a un mismo directorio.

## GPU y LLM opt-in (marker)

Por default `marker` corre **CPU only y sin LLM remoto** — coherente con
la filosofía local-first del toolkit. Para acelerar y mejorar layout
en PDFs complejos:

```bash
JW_MARKER_USE_GPU=1 \
JW_MARKER_USE_LLM=1 \
OPENAI_API_KEY=sk-... \
    jw rag ingest-pdf ~/Documents/atalaya_dificil.pdf
```

`use_llm=True` envía fragmentos del documento al modelo configurado
(OpenAI/Anthropic según `marker`'s config). Sólo activarlo cuando el
usuario sabe que el contenido es público y la mejora vale el costo.

## Metadata por chunk

Cada chunk producido por estos loaders trae como mínimo:

```jsonc
{
  "source_kind": "pdf_marker" | "office_markitdown",
  "source_path": "/abs/path/file.pdf",
  "source_format": "pdf" | "docx" | "pptx" | "xlsx",  // solo office
  "file_hash":   "<sha256 completo>",
  "language":    "es",
  "is_jw":       true,    // solo pdf_marker
  "para_count":  3,        // del ParagraphChunker
  "chunker":     "paragraph"
}
```

`custom_meta` adicional se mergea encima (ej. `{"sender": "hermano_pablo"}`).

## Limitaciones

- **Tablas complejas**: `marker` hace su mejor esfuerzo, ocasionalmente
  pierde celdas mergeadas. Verificar manualmente si el corpus depende
  de ellas.
- **OCR de escaneos baja resolución**: < 150 DPI puede dar texto basura.
  Re-escanear a 300 DPI antes de ingerir.
- **Cifrado**: PDFs cifrados con contraseña fallan — descifrar primero.
- **Office macros**: `markitdown` ignora macros; el contenido visible
  se extrae correctamente.
- **PDFs sólo-imagen sin OCR**: pendiente fallback a Tesseract en una
  fase posterior; por ahora el loader devuelve un markdown vacío y
  cero chunks.
