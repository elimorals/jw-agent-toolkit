# jw-core-js (Fase 47, MVP v0.1)

TypeScript port of `jw-core` for surfaces that cannot ship a Python runtime:
the WOL browser extension (Fase 48), a future Capacitor mobile app, the
documentation site if it ever needs client-side parsing.

## What ships in this MVP

A narrow, opinionated subset of `jw-core` — the pieces that the rest of the
toolkit reuses dozens of times per request:

- **Reference parser** (`parseReference`, `parseAllReferences`,
  `ReferenceParser`): the same multi-language regex strategy as the Python
  port, with longest-first alternation so "1 Corintios" beats "Corintios".
- **`BibleRef`** class with `display()`, `wolUrl(lang, pub?)` and
  `toJSON()`. The JSON shape mirrors the Python Pydantic model for IPC.
- **`BOOKS`** — 66-book canonical table in en/es/pt, generated from
  `packages/jw-core/src/jw_core/data/books.py`.
- **`getLanguageConfig(lang)`** — WOL URL building blocks (`r1`/`r4`/`r5`,
  `lp-e`/`lp-s`/`lp-t`, `nwtsty`/`nwt`).
- **Versification mapping (Fase 46 port)**: `toCanonical(args)`, `explain(args)`,
  `loadCatalog()`. Same catalog JSON as the Python implementation.

The package builds dual **ESM + CJS** with TypeScript declarations
(`tsup`). It is published as `@jw-agent-toolkit/core` to npm.

## Parity contract

`shared/data/bible_references_golden.json` is the single source of truth.
Both implementations run it as a parameterized test:

| Side | File | Tests in MVP |
|---|---|---|
| Python | `packages/jw-core/tests/test_golden_fixture_parity.py` | 17 |
| TypeScript | `packages/jw-core-js/tests/parser.test.ts` | 17 (plus 23 extra in the suite) |

A drift on either side fails CI. When the Python `BOOKS` table grows, the
JSON sibling is regenerated and the JS package picks up the new aliases.

## Test coverage today

- **TypeScript (Vitest)**: 40 tests, all green. Parser, longest-first
  alternation, multi-ref extraction, WOL URL builder (en/es), `display`,
  `toJSON`, versification (catalog load + identity + Joel + Malachi +
  round-trip + unknown tradition + trilingual explain).
- **Python (pytest)**: 17 new parity tests, all green. Plus the 1005 jw-core
  tests that already cover the underlying parser implementation.

## What is intentionally pending (post-MVP roadmap)

> **Status update F56 (2026-06-03)**: tras auditoría, los buckets A–E
> quedan **diferidos** salvo que aparezca una app Capacitor real en
> `apps/`. Hoy F48 sólo usa `displayName` + tipo `Language` (~5% del
> MVP); el resto no tiene consumidores. Lo que sí se ejecuta como F56
> aparece arriba en la sección "Estado de buckets post-MVP".
>
> Las descripciones de los buckets A–E debajo se mantienen como
> referencia histórica y guía para cuando llegue Capacitor.

The Fase 47 spec lists 123 tasks total. The MVP covers the first ~20
(scaffold + parser + BibleRef + WOL URL + book table + versification +
fixture + Vitest + Python parity). The remaining buckets:

### Bucket A — extra parsers

| What | Effort | Why it matters |
|---|---|---|
| `parseVerse` (extract a single verse from HTML) | Medium | Lets the extension show the verse text inline |
| `parseStudyNotes` (parse nwtsty study notes) | Medium | Inline annotations |
| `parseCrossReferences` | Small | Cross-ref panel client-side |
| `parseArticle` (Watchtower / Awake articles) | Large | Re-uses BeautifulSoup logic in Python |

### Bucket B — HTTP clients

| What | Effort | Why it matters |
|---|---|---|
| WOLClient (`fetch`, `getBibleChapter`) | Medium | Removes the round-trip via the Python REST server for the most common calls |
| CDNClient (`search`) | Medium | Inline search dropdown in the extension |
| TopicIndexClient | Medium | Topic-index hits for the apologetics agent surface |

### Bucket C — JWPUB / EPUB

| What | Effort | Why it matters |
|---|---|---|
| `parseJwpub` (AES-128-CBC decrypt + ZIP) | Large | Capacitor app can open .jwpub files offline |
| `parseEpub` | Medium | Same |

The two parsers carry the cryptographic core of the toolkit; a TypeScript
port needs the Web Crypto API and careful testing against the Python golden
fixtures.

### Bucket D — Operational primitives

| What | Effort | Why it matters |
|---|---|---|
| `DiskCache` equivalent (IndexedDB) | Medium | Browser-side response cache |
| `Throttler` (Token bucket) | Small | Friendly to wol.jw.org rate limits |
| Telemetry opt-in | Small | Parity with Python instrumentation |
| Provenance models (Fase 40 port) | Small | `Citation.metadata` shape parity |

### Bucket E — Multi-locale

The MVP ships en/es/pt only. Python now bundles 17 locales via
`jw_core.data.book_locales`. Porting them is a matter of regenerating
`shared/data/bible_books.json` with `CORE` widened to the full set and
re-running the parity suite. No code changes expected.

## How to extend

1. Edit `packages/jw-core/src/jw_core/data/books.py` (add aliases / a
   language).
2. Run the dump script:

   ```bash
   PP=$(find packages -maxdepth 3 -type d -name src | tr '\n' ':') \
   PYTHONPATH=$PP .venv/bin/python -c "
   import json
   from jw_core.data.books import BOOKS
   CORE = {'en', 'es', 'pt'}
   out = [
     {'num': b['num'], 'canonical': b['canonical'],
      'names': {k: v for k, v in b['names'].items() if k in CORE}}
     for b in BOOKS
   ]
   json.dump({'version': '1.0', 'languages': sorted(CORE), 'books': out},
             open('shared/data/bible_books.json', 'w'),
             ensure_ascii=False, indent=2)
   "
   cp shared/data/bible_books.json packages/jw-core-js/src/books.json
   ```

3. Run both test suites:

   ```bash
   uv run pytest packages/jw-core/tests/test_golden_fixture_parity.py
   cd packages/jw-core-js && npm test
   ```

## Estado de integración con Fase 48 (WOL extension)

**Completada** en commit `8ed5901`. La extensión consume el paquete vía
`file:../../packages/jw-core-js` declarado en `dependencies` (no
`optionalDependencies` como decía el plan original — la dep es
mandatoria; ya no hay parser local de nombres de libros).

APIs efectivamente usadas hoy desde `apps/wol-browser-extension/src/dom/verse_detector.ts`:

- `displayName(bookNum, lang)` — resuelve nombre localizado de 66 libros.
- tipo `Language` — anotaciones de tipo.

Lo que F48 **no** usa del MVP (porque vive in-page con el DOM cargado):

- `parseReference` / `parseAllReferences` — la ext detecta versículos
  por DOM (`span.v`), no por texto libre.
- `BibleRef.wolUrl()` — la ext ya está dentro de WOL.
- `toCanonical` / `explain` — no expone discrepancias de versificación.

## Receta 12 (Capacitor) cookbook

`docs/cookbook/12-capacitor-app.md` **no tiene marker `skip-until-fase`**
y pasa desde el MVP. Es un guardián de metadata: valida que el shape
de `package.json` con `@capacitor/core` declarado sea coherente y que
`bible_references_golden.json` contenga "Juan 3:16". **No instala
Capacitor ni compila para iOS/Android.** Es una promesa estática.

## Estado de buckets post-MVP

Auditoría F56 (2026-06-03): los buckets A/B/C/D/E del plan formal están
**diferidos** porque la única justificación real (app Capacitor móvil)
es vaporware — cero código en `apps/`, `capacitor.config.ts` no existe,
VISION.md no la menciona. F49 second-brain explicita "mobile compile
remoto vía REST API de jw-mcp" como estrategia móvil del proyecto.

Lo que sí se ejecuta como F56:

- Fix ROADMAP (esta sección, las antes mentían).
- Quick win F48 (dedup tipo `Language`).
- Ampliar `bible_references_golden.json` a ≥100 casos + verificar
  `detectedLanguage` (el campo no se chequeaba antes — drift silencioso).
- Workflow `cross-lang.yml` CI bloqueante (el contrato anti-drift que
  el plan prometía).
- Mini-bucket nuevo: `BibleRef.fromWolUrl(href)` + `langFromWolPath(href)`,
  inverso puro de `wolUrl()`. Permite a F48 ahorrar ~50 LOC de regex
  propias. Sin Web Crypto, sin fetch.

Cuando aparezca código real Capacitor, reabrir los buckets en orden
A → B → C.
