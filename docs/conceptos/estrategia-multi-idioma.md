# Estrategia multi-idioma

> Cómo el toolkit modela los idiomas de jw.org, qué nivel de soporte da a cada uno y dónde están los puntos de cuidado.

## Tres niveles de soporte

| Nivel | Qué se soporta | Idiomas actuales |
|---|---|---|
| **Nivel 1** | Parser de citas + construcción de URLs + herramientas MCP completas | `en`, `es`, `pt` |
| **Nivel 2** | Construcción de URLs (capítulos, búsqueda, descargas) | Cualquier idioma registrado en `languages.py` |
| **Nivel 3** | Fallback elegante: se acepta el parámetro y se devuelve resultado | Cualquiera (fallback a inglés) |

## Registro central: `jw_core.languages`

Toda la información por idioma vive en un dataclass `Language`:

```python
@dataclass(frozen=True)
class Language:
    iso: str                # ISO-639-1 lowercase ("en", "es", "pt")
    jw_code: str            # JW internal code ("E", "S", "T")
    lp_tag: str             # wol.jw.org URL tag ("lp-e", "lp-s", "lp-t")
    display: str            # Human-readable name
    wol_resource: str       # `r1`/`r4`/etc. token en URLs WOL
    default_bible: str      # Biblia por defecto para este idioma
```

El registro actual:

```python
"en": Language(iso="en", jw_code="E", lp_tag="lp-e", display="English",
               wol_resource="r1", default_bible="nwtsty"),
"es": Language(iso="es", jw_code="S", lp_tag="lp-s", display="Spanish",
               wol_resource="r4", default_bible="nwt"),
"pt": Language(iso="pt", jw_code="T", lp_tag="lp-t", display="Portuguese",
               wol_resource="r5", default_bible="nwt"),
```

### Resolución flexible

`get_language(iso_or_jw)` acepta tanto ISO como código JW:

```python
get_language("es")  # → Language(iso="es", ...)
get_language("S")   # → mismo objeto
get_language("en")  # → Language(iso="en", ...)
get_language("E")   # → mismo objeto
```

Si el idioma no existe, lanza `KeyError`.

## Tres convenciones de código

JW usa simultáneamente tres notaciones distintas. Saber cuál usar en cada API es crítico:

| API | Convención | Ejemplo (español) |
|---|---|---|
| URLs `jw.org` (lista de idiomas, etc.) | ISO 639-1 | `es` |
| URLs `wol.jw.org` (path inicial) | ISO 639-1 | `es` |
| URLs `wol.jw.org` (lp-tag) | `lp-{ISO}` | `lp-s` |
| API CDN (`b.jw-cdn.org/apis/search/...`) | JW code | `S` |
| `GETPUBMEDIALINKS` (`langwritten=`) | JW code | `S` |
| `data.jw-api.org/mediator/v1/languages/{X}/web` | JW code | `S` |

Por eso muchas herramientas MCP aceptan `language="en"` (ISO) pero internamente llaman a `get_language(...).jw_code` para hablar con la CDN.

## Por qué `wol_resource` y `default_bible` por idioma

**Descubrimiento de Fase 2**: el MVP inicial (Fase 1) generaba URLs como:

```
https://wol.jw.org/es/wol/b/r1/lp-s/nwtsty/43/3   # ← INCORRECTO
```

Esto da 404. La URL correcta en español es:

```
https://wol.jw.org/es/wol/b/r4/lp-s/nwt/43/3      # ← CORRECTO
```

Diferencias:

- `r1` vs `r4`: la versión del bundle de recursos WOL difiere por idioma. Inglés tiene `r1`, español `r4`, portugués `r5`. Estos cambian con el tiempo; cuando un sitio se reorganiza, el número aumenta.
- `nwtsty` vs `nwt`: la Edición de Estudio (Study) solo está disponible en inglés actualmente. Otros idiomas usan la edición estándar `nwt`.

La corrección fue mover `wol_resource` y `default_bible` al dataclass `Language` y dejar que cada cliente y modelo los lean desde ahí.

## Parser de citas multi-idioma

`parse_reference("Juan 3:16")` funciona porque:

1. **`jw_core.data.books.BOOKS`** tiene una entrada por libro con un dict `names: {"en": [...], "es": [...], "pt": [...]}`. Cada entrada lista el nombre canónico + abreviaturas.
2. **`ReferenceParser`** construye una regex maestra a partir de TODAS las formas en TODOS los idiomas, ordenadas de mayor a menor longitud.
3. **`_norm`** normaliza acentos (`Génesis` → `genesis`) y minúsculas antes del match.
4. Cuando matchea, el lookup `_index[normalized_key]` devuelve `(book_num, lang, canonical)`.

```python
BOOKS = [
    {"num": 43, "canonical": "John",
     "names": {"en": ["John", "Joh", "Jn"],
               "es": ["Juan", "Jn", "Jua"],
               "pt": ["João", "Joã", "Jo"]}},
    ...
]
```

### Limitación conocida: colisiones ortográficas

Cuando dos idiomas comparten una forma idéntica tras `_norm` (NFD-strip + lowercase), gana el primer idioma registrado para `detected_language`. Ejemplos:

- "Corintios" (es) ≈ "Coríntios" (pt) → ambos normalizan a `corintios`.
- "Job" (en/es) ≈ "Job" (pt en lista alternativa).
- "Salmos" (es) ≈ "Salmos" (pt).

El número de libro **siempre es correcto** porque coincide entre idiomas. Solo `detected_language` puede confundirse. En la práctica esto solo afecta a la lógica que cambia comportamiento basada en idioma detectado (raro — normalmente el usuario provee `lang` explícitamente).

## Añadir un nuevo idioma

1. **Añadir entrada a `_REGISTRY`** en `jw_core/languages.py`:

```python
"fr": Language(iso="fr", jw_code="F", lp_tag="lp-f", display="French",
               wol_resource="r2",  # verifica con curl
               default_bible="nwt"),
```

2. **Añadir nombres en cada libro** de `jw_core/data/books.py`:

```python
{"num": 43, "canonical": "John",
 "names": {"en": [...], "es": [...], "pt": [...],
           "fr": ["Jean", "Jn"]}},
```

3. **El `BookNames` TypedDict** debe extenderse con el nuevo idioma:

```python
class BookNames(TypedDict):
    en: list[str]
    es: list[str]
    pt: list[str]
    fr: list[str]  # nuevo
```

4. **El parser re-indexa automáticamente** al importarse (no hay caché persistente).

5. **Verificar URLs**: hacer un `curl -I` para confirmar `wol_resource` y `default_bible`. Si la edición de estudio existe en ese idioma, ponerla; si no, dejar `nwt`.

## El caso del usuario en español

El proyecto tiene un sesgo deliberado hacia español (el autor lo usa así):

- `jw daily` por defecto usa `--lang es`.
- `jw verse` por defecto usa `--lang es`.
- Las skills tienen `Default to Spanish` en sus instrucciones.
- Las herramientas MCP que sí toman `language="en"` por defecto lo hacen por compatibilidad con clientes en inglés; el usuario en español pasa `language="es"` explícitamente o `language="S"`.

## Detección automática de idioma

Hoy en día **no hay detección automática del idioma del query**. El parser solo detecta el idioma del **nombre del libro** (porque ahí sí está en BOOKS). Para cualquier otra cosa (texto libre, snippets), el caller debe proveer `language=`.

Razón: detección automática añade dependencias pesadas (langdetect, fasttext) y errores difíciles de depurar para casos cortos. Hasta tener un caso de uso claro, no se incluye.
