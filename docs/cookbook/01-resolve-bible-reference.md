# Resolver una referencia bíblica

> **Tiempo estimado**: 2 minutos
> **Requisitos**: jw-core (siempre disponible)
> **Slug URL**: `/cookbook/01-resolve-bible-reference`

## ¿Qué construyes?

Parsear cadenas tipo `"Juan 3:16"`, `"Genesis 1:1-3"` o `"1 Co 13:4"` en una estructura `BibleRef` con número de libro canónico, capítulo y versículos.

## Código (copy-pasteable)

```python
# test
from jw_core import parse_reference

ref = parse_reference("Juan 3:16")
assert ref is not None
assert ref.book_canonical == "John"
assert ref.book_num == 43
assert ref.chapter == 3
assert ref.verse_start == 16

# Funciona en es/en/pt — la detección de idioma es automática.
es = parse_reference("Génesis 1:1")
en = parse_reference("Genesis 1:1")
assert es.book_num == en.book_num == 1

# Rangos:
r = parse_reference("Mateo 5:3-12")
assert r.verse_start == 3
assert r.verse_end == 12

# No referencia → None
assert parse_reference("hola, no soy una referencia") is None
```

## Por qué funciona

`parse_reference` interna usa un detector multilenguaje que conoce los nombres de los 66 libros bíblicos en en/es/pt + abreviaciones canónicas. Devuelve `None` (no excepción) cuando no encuentra match, lo que hace seguro encadenarlo en un agente sin try/except.

## Variaciones

- `parse_all_references(text)` — devuelve la lista completa, útil para extraer todas las citas de un párrafo.
- `ref.display(lang="es")` — render legible.
- `ref.has_verse` — bool para diferenciar "Juan 3" de "Juan 3:16".

## Próximo paso

→ [02 — Buscar y sintetizar](02-search-and-synthesize.md)
