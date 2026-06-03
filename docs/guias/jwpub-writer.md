# Guía — Generador de publicaciones .jwpub (Fase 50)

> Empaquetar HTML+media como un archivo `.jwpub` cifrado que **JW Library
> nativo puede importar y leer**. Cierra el ciclo simétrico de la Fase 5.5
> (descifrado).

## ¿Cuándo necesito esto?

- **Empaquetar golden fixtures** del finetune como publicación instalable
  en tu dispositivo para verificación humana.
- **Distribuir traducciones custom** producidas por el agente
  cross_lingual_research (F55.7) en un formato que la app oficial
  consume.
- **Empaquetar datasets** de Q&A para revisión por congregación sin
  exponer archivos sueltos.
- **Anotaciones agregadas** como una capa visible junto a la
  publicación original.

> ⚠️ No es para distribución masiva ni copia de contenido de jw.org. El
> writer no es un "reempaquetador" de publicaciones existentes — es
> para contenido que tú generas y quieres llevar al ecosistema JW
> Library de forma legible.

## Algoritmo (heredado de html2jwpub MIT)

```
INPUT  : carpeta con *.html y subcarpetas de media
                         │
                         │ JwpubBuilder.add_document(...)
                         │ JwpubBuilder.add_media(...)
                         ▼
SQLite (en memoria + backup)
  Tablas: Publication, RefPublication, Document, TextUnit,
          PublicationViewItem, Multimedia, DocumentMultimedia...
                         │
                         │ encrypt_blob(content, key, iv)
                         │   key, iv = compute_key_iv(lang_idx, symbol,
                         │                            year, issue_tag)
                         │   key = SHA-256(pub_str) XOR XOR_KEY [:16]
                         │   iv  = SHA-256(pub_str) XOR XOR_KEY [16:]
                         │   content = zlib_deflate(html)
                         │   blob = AES-128-CBC(content_padded, key, iv)
                         │
                         │ outer ZIP
                         │   manifest.json (SHA-256 contents)
                         │   contents (inner ZIP)
                         │     {symbol}.db (SQLite cifrado)
                         │     {media files}
                         ▼
OUTPUT : .jwpub instalable en JW Library
```

`XOR_KEY` es la constante mágica `11cbb558...5ada7` que JW embebe en sus
binarios. Misma constante usada por el descifrado de F5.5.

## CLI

```bash
# Estructura esperada:
mi-pub/
├── chapter1.html
├── chapter1/          ← opcional: media del chapter1.html
│   ├── image.jpg
│   └── audio.mp3
├── chapter2.html
└── chapter3.html

# Empaquetar:
jw jwpub build mi-pub/ \
    --out mi-pub.jwpub \
    --symbol ex22 \
    --title "Mi Publicación Ejemplo" \
    --year 2022 \
    --lang 0
```

Flags:
- `--symbol` / `-s`: el "symbol" JW (`w22`, `bh`, `nwt`, `ex22`...). Sé
  conservador con la colisión: no uses uno que ya existe en JW Library
  o sobrescribirá la entrada.
- `--title` / `-t`: título mostrado en la app.
- `--year` / `-y`: año de publicación.
- `--lang` / `-l`: índice MEPS del idioma (0 = English, 1 = Spanish,
  ver `jw_core.data.book_locales` para la lista).
- `--issue` (opcional): para periódicos. Ejemplo Atalaya junio 2022:
  `--issue 20220600`. Si lo omites, el campo es 0 (publicación de
  edición única).

## Inspección post-build

`jw jwpub inspect <path>` lee el archivo recién generado (modo
metadata o `--extract` para imprimir texto descifrado).

```bash
jw jwpub inspect mi-pub.jwpub
# JWPUB · mi-pub.jwpub
# Mi Publicación Ejemplo
# symbol=ex22  year=2022  type=Manual/Guidelines
# documents=3  decrypted=False
#  # │ Chapter │ Title          │ Paragraphs │ Pages
# ───┼─────────┼────────────────┼────────────┼──────
#  0 │         │ chapter1       │ 254        │ 1-1
#  1 │         │ chapter2       │ 254        │ 1-1
#  2 │         │ chapter3       │ 254        │ 1-1
```

## API Python

```python
from pathlib import Path
from jw_core.writers.jwpub import JwpubBuilder

builder = JwpubBuilder(
    symbol="ex22",
    title="Mi Publicación Ejemplo",
    year=2022,
    meps_language_index=0,
)

# Añadir documentos (HTML)
builder.add_document(
    title="Capítulo 1",
    content="<html><body><p data-pid='1'>Texto del primer párrafo...</p></body></html>",
)

# Documentos con media
img_path = Path("portada.jpg")
builder.add_document(
    title="Capítulo 2",
    content="<html><body><p>Ver imagen.</p></body></html>",
    media=[img_path],
)

# Empaquetar
out = builder.build(Path("mi-pub.jwpub"))
print(f"Wrote {out}")
```

### Round-trip programático

Verificar lo que se escribió:

```python
from jw_core.parsers.jwpub import parse_jwpub

parsed = parse_jwpub(out)
assert parsed.symbol == "ex22"
assert parsed.document_count == 2
for doc in parsed.documents:
    print(doc.title, doc.text[:80])
```

`parse_jwpub` usa el mismo `compute_key_iv()` del módulo crypto
compartido — el round-trip es lossless.

## Módulo compartido `jw_core.jwpub_crypto`

Para casos avanzados (calcular el key/iv manualmente, descifrar bytes
sueltos sin pasar por el parser completo), está la API pública:

```python
from jw_core.jwpub_crypto import (
    XOR_KEY,         # bytes — la constante mágica 32-byte
    compute_key_iv,  # (lang, symbol, year, issue=0) → (key, iv)
    encrypt_blob,    # (content, key, iv) → bytes (cifrado para Content)
    decrypt_blob,    # (blob, key, iv) → str (HTML)
)

key, iv = compute_key_iv(0, "w22", 2022, 20220600)
print(f"Watchtower Jun 2022 EN key={key.hex()}, iv={iv.hex()}")
```

## Limitaciones reconocidas

- **No genera índices FTS** del contenido (SearchIndexDocument tabla
  queda vacía). JW Library reconstruye índices al importar, así que la
  publicación aparece normal pero la búsqueda local puede ser más
  lenta los primeros segundos.
- **No genera footnotes/citations** estructuradas. El HTML que pasas se
  empaqueta literal — referencias bíblicas en el texto no se vuelven
  links clickeables en JW Library.
- **Schema version fija en 8.** JW Library nativo lee schemas 1-8+; v8
  es estable y conservador.
- **MepsBuildNumber fijo en 12345.** Es un campo cosmético; no afecta
  la lectura.

## Tests

`packages/jw-core/tests/test_jwpub_writer.py` (9 tests):

- Round-trip básico builder → parser.
- Round-trip por tamaño de contenido (parametrizado 10/100/1000/10000
  chars) — cubre el boundary case donde `len(deflated) % 16 == 0` y
  PKCS7 añade un bloque entero.
- Publicación con `issue_tag_number` (Watchtower con número de issue).
- Media bundled en el inner ZIP.

## Crédito y licencia

Algoritmo portado de `darioragusa/html2jwpub` (Swift, MIT). El schema
SQLite (`packages/jw-core/src/jw_core/data/jwpub_schema.sql`) es
también herencia directa.

Constante XOR descubierta originalmente por `gokusander/jwpub-toolkit`
(MIT) por inspección del binario de JW Library.

Ver `README.md` raíz para atribuciones completas.
