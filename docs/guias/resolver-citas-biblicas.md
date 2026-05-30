# Guía: resolver citas bíblicas

> Cómo usar `parse_reference` para convertir texto en lenguaje natural a una cita estructurada con URL canónica de wol.jw.org.

## Caso básico

```python
from jw_core import parse_reference

ref = parse_reference("Juan 3:16")
print(ref.display())                # "John 3:16"
print(ref.book_num)                 # 43
print(ref.book_canonical)           # "John"
print(ref.chapter)                  # 3
print(ref.verse_start)              # 16
print(ref.verse_end)                # None
print(ref.detected_language)        # "es"
print(ref.raw_match)                # "juan 3:16"
print(ref.wol_url(lang="es"))
# → "https://wol.jw.org/es/wol/b/r4/lp-s/nwt/43/3#study=discover&v=43:3:16"
```

Si no encuentra ninguna referencia, devuelve `None`:

```python
parse_reference("Hola mundo")       # None
parse_reference("")                  # None
```

## Múltiples citas en un texto

`parse_all_references(text)` devuelve **todas** las citas encontradas en orden.

```python
from jw_core import parse_all_references

refs = parse_all_references(
    "Comparemos Juan 3:16 con 1 Juan 4:8 y Gen 1:1"
)
for r in refs:
    print(r.display(), "→", r.wol_url(lang="es"))

# John 3:16 → https://wol.jw.org/es/wol/b/r4/lp-s/nwt/43/3#study=discover&v=43:3:16
# 1 John 4:8 → https://wol.jw.org/es/wol/b/r4/lp-s/nwt/62/4#study=discover&v=62:4:8
# Genesis 1:1 → https://wol.jw.org/es/wol/b/r4/lp-s/nwt/1/1#study=discover&v=1:1:1
```

## Rangos de versículos

El parser soporta rangos con `-`, `–`, `—`:

```python
ref = parse_reference("1 Corintios 13:4-7")
print(ref.verse_start)  # 4
print(ref.verse_end)    # 7
print(ref.verse_range)  # "4-7"
print(ref.display())    # "1 Corinthians 13:4-7"
```

## Formas reconocidas

Por cada libro, el parser acepta:

- **Nombre completo** en inglés, español y portugués.
- **Abreviaturas estándar JW** (ver `jw_core/data/books.py`).
- **Variantes con/sin espacio** entre el número y el nombre para libros como "1 Juan" / "1Juan".
- **Mayúsculas indiferentes**.
- **Acentos indiferentes** (gracias a `_norm` que aplica NFD-strip).
- **Separadores** entre capítulo y versículo: `:` o `.` (con espacios opcionales).

Ejemplos válidos:

```python
parse_reference("Juan 3:16")
parse_reference("juan 3:16")
parse_reference("JUAN 3:16")
parse_reference("Jn 3:16")
parse_reference("Jua 3:16")
parse_reference("Juan 3.16")
parse_reference("Juan 3 : 16")
parse_reference("Génesis 1:1")
parse_reference("Genesis 1:1")
parse_reference("Gn 1:1")
parse_reference("1Co 13:4-7")
parse_reference("1 Co 13:4-7")
parse_reference("1 Corintios 13:4-7")
parse_reference("Apocalipsis 21:1")
parse_reference("Ap 21:1")
parse_reference("Revelation 21:1")
parse_reference("Re 21:1")
```

## Capítulo solo (sin versículo)

```python
ref = parse_reference("Hebreos 13")
print(ref.has_verse)     # False
print(ref.verse_range)   # ""
print(ref.wol_url(lang="es"))
# → "https://wol.jw.org/es/wol/b/r4/lp-s/nwt/58/13"  (sin ancla #v=...)
```

## Idiomas detectados vs idiomas de URL

`ref.detected_language` indica **qué idioma usó el parser** para reconocer el libro. `ref.wol_url(lang=...)` controla **qué idioma usa la URL**. Son ortogonales:

```python
ref = parse_reference("Juan 3:16")
print(ref.detected_language)        # "es" (porque "Juan" es español)

# Pero podemos construir URL en cualquier idioma soportado:
ref.wol_url(lang="en")  # → URL al capítulo 3 de John en inglés
ref.wol_url(lang="pt")  # → URL al capítulo 3 de João en portugués
```

## Colisiones ortográficas conocidas

Cuando dos idiomas comparten una forma idéntica tras `_norm`, gana el **primer idioma registrado** en `BOOKS`. Por ejemplo:

- "Corintios" (es) ≈ "Coríntios" (pt) → ambos normalizan a `corintios`. Como `es` aparece antes que `pt` en cada entrada `BOOKS`, el parser reporta `detected_language="es"` para ambos.
- "Job" (en/es) ≈ "Job" (pt como alternativa) → `en` gana.
- "Salmos" (es) ≈ "Salmos" (pt) → `es` gana.

**El número de libro siempre es correcto** porque coincide entre idiomas. Solo `detected_language` puede confundirse. En la práctica raramente importa; si necesitas el idioma del usuario, pásalo explícitamente.

## Casos límite

### Texto sin separador entre número y libro

El parser acepta `1Juan` y `1 Juan` por igual gracias al regex `\s*` entre el número y el nombre, pero requiere que el nombre normalizado **exista** en `BOOKS` con esa forma:

```python
parse_reference("1Juan 4:8")     # ✓ match
parse_reference("1 Juan 4:8")    # ✓ match
parse_reference("1.Juan 4:8")    # ✗ no match (el punto entre "1" y "Juan" no se acepta)
```

### Texto antes/después de la cita

El parser ignora cualquier texto alrededor:

```python
refs = parse_all_references(
    "El versículo más conocido es Juan 3:16. También Gen 1:1 importa."
)
# → [BibleRef(John 3:16), BibleRef(Genesis 1:1)]
```

### Word boundary

El parser usa `\b` antes del nombre del libro para evitar matches en mitad de palabra:

```python
parse_reference("rejudge 3:4")   # None ("judge" no matchea a mitad de "rejudge")
parse_reference("Judge 3:4")     # ✓ Judges 3:4
```

## Cómo el parser construye su índice

(Solo relevante si vas a extenderlo — ver [`extender-el-parser.md`](extender-el-parser.md))

En tiempo de import (lazy via `lru_cache(maxsize=1)`):

1. Lee `BOOKS` de `jw_core/data/books.py`.
2. Para cada libro, para cada idioma, para cada nombre alternativo:
   - Calcula `display = _norm(name).strip()` (lowercase + accent-strip).
   - Calcula `key = _norm_key(name)` (lo anterior + quita espacios, puntos, guiones).
   - Guarda `_index[key] = (book_num, lang, canonical)` con `setdefault` (la primera entrada gana en colisiones).
3. Compila una regex maestra con todas las `display` formas, ordenadas longest-first.
4. Cachea el `ReferenceParser` como singleton de proceso.

El singleton no se reconstruye nunca durante la vida del proceso. Si modificas `BOOKS` en runtime (raro), tienes que `_singleton.cache_clear()` y volver a llamar.

## Anti-patrones

### No hagas búsqueda case-sensitive

```python
# MAL: depender de la capitalización
if "Juan" in text:
    ref = parse_reference(text)

# BIEN: dejar que el parser maneje todo
ref = parse_reference(text)
if ref is None:
    ...
```

### No construyas URLs manualmente

```python
# MAL: hardcodear el patrón
url = f"https://wol.jw.org/es/wol/b/r1/lp-s/nwtsty/{book_num}/{ch}"
#                              ^^ INCORRECTO: r1 es inglés, español es r4
#                                        ^^^^^^^ INCORRECTO: nwtsty es solo inglés

# BIEN: dejar que BibleRef.wol_url use el registro
url = ref.wol_url(lang="es")
```

### No asumas que el parser detecta el idioma del query

El parser solo detecta el idioma del **nombre del libro**. Para queries libres (búsqueda, RAG), pásale el idioma explícito.

## Ver también

- [`extender-el-parser.md`](extender-el-parser.md) — añadir idiomas o abreviaturas
- [`docs/conceptos/estrategia-multi-idioma.md`](../conceptos/estrategia-multi-idioma.md) — niveles de soporte, colisiones
- [`docs/referencia/jw-core.md`](../referencia/jw-core.md) — referencia exhaustiva del parser
