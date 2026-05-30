# Referencia: jw-cli

> Documentación exhaustiva de cada comando del CLI, sus opciones, formato de salida y códigos de salida.

## Estructura del paquete

```
jw_cli/
├── __init__.py
├── main.py                # Typer app + registro de subcomandos
└── commands/
    ├── verse.py
    ├── chapter.py
    ├── daily.py
    ├── search.py
    ├── languages.py
    ├── download.py
    ├── jwpub.py           # Fase 10 — inspect/decrypt JWPUB local
    └── topic.py           # Fase 10 — search topic index + fetch top subject
```

El entry point está en `pyproject.toml`:

```toml
[project.scripts]
jw = "jw_cli.main:app"
```

Tras `uv sync` se instala como `uv run jw <subcomando>`.

---

## Comando `jw verse`

Parsea una referencia bíblica y muestra estructura canónica + URL.

```bash
jw verse <reference> [--lang LANG]
```

### Argumentos

| Nombre | Tipo | Descripción |
|---|---|---|
| `reference` | str | Cita bíblica (`"Juan 3:16"`, `"1 Co 13:4-7"`, ...) |

### Opciones

| Flag | Default | Descripción |
|---|---|---|
| `--lang`, `-l` | `"es"` | ISO code para la URL (`en`/`es`/`pt`) |

### Salida (rica con Rich Table)

```
        Reference  John 3:16
           Book #  43
          Chapter  3
         Verse(s)  16
    Detected lang  es
          Matched  'juan 3:16'

https://wol.jw.org/es/wol/b/r4/lp-s/nwt/43/3#study=discover&v=43:3:16
```

### Códigos de salida

| Código | Significado |
|---|---|
| `0` | OK |
| `1` | No se detectó cita bíblica en la entrada |

---

## Comando `jw chapter`

Descarga y muestra un capítulo bíblico desde wol.jw.org.

```bash
jw chapter <book_num> <chapter> [--lang LANG] [--pub PUB] [--max N]
```

### Argumentos

| Nombre | Tipo | Descripción |
|---|---|---|
| `book_num` | int | 1..66 (1=Genesis, 66=Revelation) |
| `chapter` | int | Número de capítulo |

### Opciones

| Flag | Default | Descripción |
|---|---|---|
| `--lang`, `-l` | `"en"` | ISO code (en/es/pt) |
| `--pub` | `"nwtsty"` | Edición bíblica |
| `--max` | `0` | Limitar a N párrafos (0 = todos) |

### Salida

- Título del capítulo (cyan, negrita)
- URL de origen (dim)
- Párrafos en texto plano

### Códigos de salida

| Código | Significado |
|---|---|
| `0` | OK |
| `1` | `book_num` fuera de rango 1..66 |

---

## Comando `jw daily`

Muestra el texto diario de hoy.

```bash
jw daily [--lang LANG]
```

### Opciones

| Flag | Default | Descripción |
|---|---|---|
| `--lang`, `-l` | `"es"` | ISO code |

### Salida

Panel con borde cyan:

```
╭────── Daily Text ──────╮
│ Sábado 24 de mayo      │
│                        │
│ "Texto bíblico cita"   │
│                        │
│ Comentario breve...    │
│                        │
│ https://wol.jw.org/... │
╰────────────────────────╯
```

### Códigos de salida

| Código | Significado |
|---|---|
| `0` | OK |
| `1` | No se pudo extraer el texto diario del HTML |

---

## Comando `jw search`

Busca contenido en jw.org vía la API CDN.

```bash
jw search <query> [--filter FILTER] [--lang LANG] [--limit N]
```

### Argumentos

| Nombre | Tipo | Descripción |
|---|---|---|
| `query` | str | Términos de búsqueda |

### Opciones

| Flag | Default | Descripción |
|---|---|---|
| `--filter`, `-f` | `"all"` | `all` / `publications` / `videos` / `audio` / `bible` / `indexes` |
| `--lang`, `-l` | `"en"` | ISO code (convertido a JW code internamente) |
| `--limit`, `-n` | `10` | Máximo de resultados |

### Salida

Header con metadata + tabla con `#`, `Title`, `Snippet`, `URL` (truncados para legibilidad).

### Códigos de salida

| Código | Significado |
|---|---|
| `0` | OK |
| `1` | Filtro inválido o idioma desconocido |

---

## Comando `jw languages`

Lista idiomas soportados por jw.org.

```bash
jw languages [--in JW_CODE] [--web | --all] [--grep PATTERN]
```

### Opciones

| Flag | Default | Descripción |
|---|---|---|
| `--in` | `"E"` | JW code en el que se mostrarán los nombres |
| `--web` / `--all` | `--web` | Filtrar a idiomas con contenido web |
| `--grep`, `-g` | `""` | Substring filter sobre nombre/vernacular |

### Salida

Tabla con: `JW`, `ISO`, `Name`, `Vernacular`, `RTL` (`•` si aplica), `Sign` (`🤟` si aplica).

Pie: `N languages shown.`

---

## Comando `jw download`

Descarga publicaciones desde `GETPUBMEDIALINKS`.

```bash
jw download <pub_code> [--lang JW_CODE] [--format FMT] [--book N]
                       [--issue YYYYMM] [--out DIR] [--list]
```

### Argumentos

| Nombre | Tipo | Descripción |
|---|---|---|
| `pub_code` | str | Código de publicación (`"fg"`, `"nwt"`, `"rr"`, ...) |

### Opciones

| Flag | Default | Descripción |
|---|---|---|
| `--lang`, `-l` | `"E"` | JW code |
| `--format`, `-f` | `"EPUB"` | PDF / EPUB / JWPUB / MP3 / RTF / BRL |
| `--book` | `None` | Bible book 1..66 (solo para Biblia) |
| `--issue` | `None` | YYYYMM (para revistas) |
| `--out`, `-o` | `./downloads` | Directorio de salida |
| `--list` | `False` | Solo lista archivos, no descarga |

### Salida

```
Bible Teach — 1 EPUB file(s)
  • bh_E.epub  (1.2 MB)
  ↓ bh_E.epub → downloads/bh_E.epub

Downloaded 1 file(s) to downloads
```

Con `--list`: mismo header + listado, sin descargar.

### Códigos de salida

| Código | Significado |
|---|---|
| `0` | OK |
| `1` | Formato inválido, o error de PubMedia (404, etc.) |
| `2` | No hay archivos para los filtros pedidos |

---

## Comando `jw jwpub`

Inspecciona o desencripta un archivo `.jwpub` local.

```bash
jw jwpub <path> [--extract|-x] [--max N]
```

### Argumentos

| Nombre | Tipo | Descripción |
|---|---|---|
| `path` | Path | Ruta al archivo `.jwpub` (debe existir) |

### Opciones

| Flag | Default | Descripción |
|---|---|---|
| `--extract`, `-x` | `False` | Decrypta el `Content` blob y muestra los párrafos por documento |
| `--max` | `0` | Limita a los primeros N documentos (0 = todos) |

### Salida

Panel con metadata (`symbol`, `year`, `publication_type`, `document_count`, `decrypted`).

**Modo default** (sin `--extract`): tabla con `#`, `Chapter`, `Title`, `Paragraphs`, `Pages` por documento.

**Modo `--extract`**: panel verde por documento con los primeros 5 párrafos del texto decryptado.

### Códigos de salida

| Código | Significado |
|---|---|
| `0` | OK |
| `1` | `JwpubError` (archivo inválido) |

---

## Comando `jw topic`

Busca en el Índice de Publicaciones Watch Tower y muestra el top subject con sus subheadings.

```bash
jw topic <query> [--lang LANG] [--limit N] [--fetch/--no-fetch] [--max-sub N]
```

### Argumentos

| Nombre | Tipo | Descripción |
|---|---|---|
| `query` | str | Tema a buscar (`"Trinity"`, `"soul"`, ...) |

### Opciones

| Flag | Default | Descripción |
|---|---|---|
| `--lang`, `-l` | `"E"` | JW code (E, S, T) |
| `--limit`, `-n` | `5` | Máximo de candidatos en el ranking |
| `--fetch` / `--no-fetch` | `--fetch` | También descarga la página completa del top subject |
| `--max-sub` | `12` | Limita los subheadings mostrados (0 = todos) |

### Salida

1. Tabla de candidatos con `#`, `Score` (0-100, ranking por título), `Title`, `docid`.
2. Con `--fetch` (default): panel con title + counts + see_also del top subject + tabla de subheadings (Level top/sub, Heading, Citations).

### Códigos de salida

| Código | Significado |
|---|---|
| `0` | OK (incluso si la query no devuelve resultados — se muestra mensaje y exit 0) |
| (no falla con código distinto) | Si el fetch del subject falla, se muestra el error y continúa |

---

## Ejemplos compuestos

### Listar EPUBs disponibles sin descargar

```bash
jw download bh --lang E --format EPUB --list
```

### Descargar Biblia entera en EPUB español

```bash
jw download nwt --lang S --format EPUB --out ./biblia-es/
```

### Capítulo de Juan en portugués

```bash
jw chapter 43 3 --lang pt
```

### Buscar "amor" solo en publicaciones, en español, top 5

```bash
jw search amor --filter publications --lang es --limit 5
```

### Texto diario en inglés

```bash
jw daily --lang en
```

### Inspeccionar TOC de un JWPUB descargado

```bash
jw download ti --lang E --format JWPUB --out ./descargas/
jw jwpub ./descargas/ti_E.jwpub
```

### Decryptar y leer los 3 primeros documentos

```bash
jw jwpub ./descargas/ti_E.jwpub --extract --max 3
```

### Buscar "Trinity" y mostrar 15 subheadings

```bash
jw topic Trinity --max-sub 15
```

### Solo ver el ranking de candidatos para "soul"

```bash
jw topic soul --no-fetch --limit 10
```
