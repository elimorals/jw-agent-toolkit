# Idiomas expandidos (Módulo 8 — Fase 16)

> Cubre el ítem #8 de [VISION.md](../VISION.md): Tier 1 → 10 idiomas, sign-language registry, traducción preservando referencias.

## Cambios al registry

`jw_core/languages.py` ahora incluye:

| ISO | JW code | lp-tag | wol_resource | default_bible |
|---|---|---|---|---|
| en | E | lp-e | r1 | nwtsty |
| es | S | lp-s | r4 | nwt |
| pt | T | lp-t | r5 | nwt |
| **fr** | **F** | **lp-f** | **r30** | **nwt** |
| **de** | **X** | **lp-x** | **r10** | **nwt** |
| **it** | **I** | **lp-i** | **r6** | **nwt** |
| **ru** | **U** | **lp-u** | **r8** | **nwt** |
| **ja** | **J** | **lp-j** | **r7** | **nwt** |
| **ko** | **KO** | **lp-ko** | **r46** | **nwt** |
| **zh** | **CHS** | **lp-chs** | **r23** | **nwt** |

`get_language("fr")` y `get_language("F")` ambos funcionan, igual que antes para los originales.

> **Nota:** los `wol_resource` para los idiomas nuevos son valores aproximados/probables; verifica una URL real (`/<iso>/wol/h/r{N}/lp-{x}`) antes de un release. Si una URL devuelve 404, ajusta el número en el registry — todos los clientes/parsers ya leen el valor desde aquí.

## Lenguas de señas

`SIGN_LANGUAGES` registra ASL/LSM/LSC/Libras con su `broadcasting_root`. Esto desbloquea (Fase posterior) la indexación de JW Broadcasting en señas — un agente futuro puede scrapear los listados de videos.

```python
from jw_core.languages import SIGN_LANGUAGES
for key, info in SIGN_LANGUAGES.items():
    print(info["display"], "→", info["broadcasting_root"])
```

## Traducción preservando referencias

VISION.md exige que cualquier traducción automática conserve las citas exactas. El nuevo módulo `jw_core/translation.py` ofrece el sandwich:

```python
from jw_core.translation import mask_references, restore_references

source = "Read John 3:16 and Romans 12:2 carefully."

# 1. Mask before sending to the LLM.
masked = mask_references(source)
print(masked.text)
# 'Read <<REF:0>> and <<REF:1>> carefully.'

# 2. The LLM translates, freely, the masked text.
translated_es = "Lee <<REF:0>> y <<REF:1>> con cuidado."

# 3. Restore in target language using the canonical BOOKS table.
final = restore_references(translated_es, masked.references, target_language="es")
print(final)
# 'Lee Juan 3:16 y Romanos 12:2 con cuidado.'
```

**Por qué este sandwich:**
1. Los LLMs son inconsistentes traduciendo nombres de libros bíblicos cuando el contexto es ambiguo ("John" → "Juan" o "Joan"?).
2. Los rangos `12:1-3` a veces se mal-traducen como `12:1 a 3`.
3. Si el LLM "ayuda" cambiando el versículo (alucinación), pierdes verificabilidad.

Con el sandwich: el LLM solo ve un token, no la cita; al final inyectamos la cita textual y canónica en el idioma destino.

`render_reference(book_num=43, chapter=3, verse_start=16, verse_end=18, language="es")` → `"Juan 3:16-18"`. Funciona para los 3 idiomas registrados en `BOOKS`; otros idiomas caen elegantemente a inglés (warning silencioso — el LLM puede pedir un BOOKS más completo).

## Cómo extender BOOKS para los 7 nuevos idiomas

`packages/jw-core/src/jw_core/data/books.py` ya tiene 66 libros × en/es/pt. Para añadir fr/de/etc:

1. Edita el `TypedDict BookNames` para añadir `fr: list[str]`.
2. Apenda los nombres en cada `BOOKS[i].names` (idealmente con 3-5 spellings/abrevs por libro).
3. El parser de referencias se autoreconstruye al import.

Esto es **trabajo de catálogo**, no de código. Cualquier publicador con conocimiento del idioma puede contribuir.

## Tests

8 tests en `packages/jw-core/tests/test_languages_module.py`:
- Tier 1 completo registrado.
- Resolution por ISO y JW code (`fr` ↔ `F`).
- Sign-language registry con broadcasting roots.
- Mask + restore roundtrip en/es preservando refs.
- Mask preserva texto sin referencias intacto.
- `render_reference` con rangos, fallback a inglés.

```bash
uv run pytest packages/jw-core/tests/test_languages_module.py -v
```

## Pendiente

- Verificar los `wol_resource` numbers en jw.org para fr/de/it/ru/ja/ko/zh.
- Añadir nombres de libros para los 7 idiomas nuevos en `BOOKS`.
- Scraper de JW Broadcasting en sign-language.
