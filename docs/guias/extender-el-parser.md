# Guía: extender el parser de referencias

> Cómo añadir un nuevo idioma, alias adicionales o manejar casos especiales del parser bíblico.

## Añadir un nuevo idioma

Ejemplo: añadir **francés** (`fr`).

### Paso 1: registrar el idioma

En `packages/jw-core/src/jw_core/languages.py`, añade una entrada al `_REGISTRY`:

```python
_REGISTRY: dict[str, Language] = {
    "en": Language(iso="en", jw_code="E", lp_tag="lp-e", display="English",
                   wol_resource="r1", default_bible="nwtsty"),
    "es": Language(iso="es", jw_code="S", lp_tag="lp-s", display="Spanish",
                   wol_resource="r4", default_bible="nwt"),
    "pt": Language(iso="pt", jw_code="T", lp_tag="lp-t", display="Portuguese",
                   wol_resource="r5", default_bible="nwt"),
    # NUEVO
    "fr": Language(iso="fr", jw_code="F", lp_tag="lp-f", display="French",
                   wol_resource="r2", default_bible="nwt"),
}
```

Cómo encontrar `wol_resource` y `default_bible`:

```bash
# Visita wol.jw.org en el idioma objetivo
open https://wol.jw.org/fr/

# Navega a un capítulo bíblico y mira la URL
# Ejemplo: https://wol.jw.org/fr/wol/b/r2/lp-f/nwt/43/3
#                                       ^^   ^^^^   ^^^
#                                       wol_  lp_   default_
#                                       resource tag bible
```

### Paso 2: extender el `TypedDict` `BookNames`

En `packages/jw-core/src/jw_core/data/books.py`:

```python
class BookNames(TypedDict):
    en: list[str]
    es: list[str]
    pt: list[str]
    fr: list[str]   # NUEVO
```

### Paso 3: añadir los 66 nombres en cada libro

Para cada uno de los 66 libros en `BOOKS`, añade la clave `"fr"`:

```python
{"num": 43, "canonical": "John",
 "names": {"en": ["John", "Joh", "Jn"],
           "es": ["Juan", "Jn", "Jua"],
           "pt": ["João", "Joã", "Jo"],
           "fr": ["Jean", "Jn"]}},   # NUEVO
```

El orden importa:
- **Índice [0]**: nombre principal de display.
- **Índices siguientes**: abreviaturas y variantes que el parser debe reconocer.

Si necesitas inspirarte, los nombres oficiales franceses están en el sitio JW de cada Biblia.

### Paso 4: verificar

```python
from jw_core import parse_reference

ref = parse_reference("Jean 3:16")
assert ref.book_num == 43
assert ref.detected_language == "fr"
assert ref.wol_url(lang="fr") == "https://wol.jw.org/fr/wol/b/r2/lp-f/nwt/43/3#study=discover&v=43:3:16"
```

El parser se re-indexa automáticamente al importarse — no hay que hacer nada más. (El singleton `_singleton()` se cachea con `lru_cache(maxsize=1)`, así que en un proceso ya en ejecución que importó `parse_reference` antes del cambio necesitarías `_singleton.cache_clear()`.)

## Añadir abreviaturas/alias a un idioma existente

Solo añade la nueva forma al array correspondiente:

```python
{"num": 19, "canonical": "Psalms",
 "names": {"en": ["Psalms", "Psalm", "Ps", "Psa"],
           "es": ["Salmos", "Salmo", "Sl", "Sal",
                  "Salm"],          # NUEVO alias
           ...}},
```

La regla: el `_norm_key` (lowercase + accent-strip + remove `\s.\-`) debe ser **único** por libro **dentro del mismo idioma**. Si dos alias normalizan a la misma key, gana el primero (no rompe, pero pueden ser redundantes).

## Manejar libros con números (1/2/3 + libro)

El parser ya soporta:

```
1 Reyes / 1Reyes / 1 Re / 1Re / 1Kings / 1 Kings / 1Ki
```

Detalles técnicos:

- En la regex maestra, las formas con espacio (`"1 reyes"`) se compilan con `\s+` entre tokens. Eso tolera `"1  Reyes"` y `"1 Reyes"`.
- Las formas sin espacio (`"1reyes"`) se compilan literalmente.
- Pueden coexistir en `BOOKS`:

```python
{"num": 11, "canonical": "1 Kings",
 "names": {"en": ["1 Kings", "1 Ki", "1Ki", "1Kgs"],  # ambas formas
           ...}}
```

## Manejar separadores no estándar

Si quieres aceptar separadores adicionales entre capítulo y versículo (hoy: `:` y `.`), modifica `_compile_master_regex` en `packages/jw-core/src/jw_core/parsers/reference.py`:

```python
# Actual:
rf"(?:\s*[:.]\s*(?P<verse_start>\d+)..."

# Para añadir `,` (riesgoso — `Jn 3,16` también puede ser un rango):
rf"(?:\s*[:.,]\s*(?P<verse_start>\d+)..."
```

⚠️ Cuidado: `,` es comúnmente usado como separador de listas en otros contextos. Probablemente no quieres aceptarlo a menos que tu idioma lo use convencionalmente para Bible refs.

## Manejar capítulos sin versículo y libros de un solo capítulo

Hoy `Hebreos 13` parsea bien (capítulo sin versículo). Para libros que solo tienen un capítulo (Obadías, Filemón, 2/3 Juan, Judas), `Filemón 5` parsea como `Filemón cap.5` (probablemente incorrecto — el usuario quiso decir versículo 5).

Solución pendiente: detectar libros mono-capítulo y forzar la interpretación de "5" como versículo. Por ahora se considera caso límite; los usuarios deben escribir `"Filemón 1:5"` explícitamente.

## Manejar el caso "Salmo X" sin número de capítulo

Como Salmos cada "capítulo" es un salmo individual, los usuarios escriben "Salmo 23" pensando en el salmo 23. Eso parsea correctamente porque Salmos = libro 19, capítulo 23.

## Limitaciones conocidas

### Colisiones ortográficas entre idiomas

`"Corintios"` (es) y `"Coríntios"` (pt) normalizan ambos a `corintios`. El primero registrado en `BOOKS["names"]` gana en `detected_language`. **El `book_num` siempre es correcto.**

Si necesitas `detected_language` exacto, pasa el idioma al cliente explícitamente y no confíes en la detección automática.

### Word boundary y palabras compuestas

El regex usa `\b` antes del nombre del libro. Esto evita:
- `"prejudgement 1:1"` → no matchea `"judge"` interno.

Pero también puede impedir:
- `"deJuan 3:16"` → no matchea (no hay word boundary entre `e` y `J`).

Esto es deliberado.

### Múltiples idiomas en un texto

`parse_all_references` puede encontrar `"Juan 3:16"` (es) y `"John 1:1"` (en) en el mismo texto, devolviendo dos `BibleRef` con `detected_language` distinto. La URL de cada uno respeta el idioma detectado solo si llamas a `ref.wol_url(lang=ref.detected_language)`; si pasas un `lang` fijo, todas las URLs salen en ese idioma.

## Tests

Las pruebas del parser están en `packages/jw-core/tests/test_reference_parser.py`. Cuando añadas un idioma:

```python
# tests/test_reference_parser.py

def test_parse_french_simple():
    ref = parse_reference("Jean 3:16")
    assert ref.book_num == 43
    assert ref.detected_language == "fr"
    assert ref.verse_start == 16

def test_parse_french_abbreviation():
    ref = parse_reference("Jn 3:16")
    # ⚠️ "Jn" existe en es, en, fr → primer registrado gana
    # Verifica cuál es para que el test no sea frágil.
```

Ejecuta:

```bash
uv run pytest packages/jw-core/tests/test_reference_parser.py -v
```

## Ver también

- [`resolver-citas-biblicas.md`](resolver-citas-biblicas.md) — uso desde código consumidor
- [`docs/conceptos/estrategia-multi-idioma.md`](../conceptos/estrategia-multi-idioma.md) — visión general
- [`docs/referencia/jw-core.md`](../referencia/jw-core.md) — referencia exhaustiva del parser
