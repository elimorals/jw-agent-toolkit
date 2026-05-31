# Fase 47 — `jw-core-js-minimal`: port TS mínimo de los 3 módulos críticos

> **Fecha**: 2026-05-31
> **Estado**: Diseño aprobado (pendiente de implementación)
> **Owner**: Elias
> **Tier**: 4 (nueva superficie JS / móvil)
> **Tamaño**: XL (~6-8 semanas)
> **Depende de**: ninguna fase. Fase 48 (browser-ext) se beneficia pero no la requiere.
> **Documento padre**: [`2026-05-31-fases-39-48-overview.md`](2026-05-31-fases-39-48-overview.md)

## Motivación

El toolkit es 100% Python (8 paquetes, ~30k LOC). Toda la superficie JS/TS que ya existe (`apps/obsidian-jw-bridge`, `apps/desktop`) **invoca la REST API de `jw-mcp`**, lo cual implica un proceso Python corriendo en localhost. Eso bloquea tres escenarios concretos:

1. **Móvil** — Capacitor/Expo no puede embeber CPython. Una app iOS/Android que resuelva "Juan 3:16" sin red necesita lógica nativa JS.
2. **Browser extension (Fase 48)** — el manifest v3 corre en sandbox, sin acceso a procesos locales. Si el toolkit no está abierto en `localhost:8765`, los botones quedan inertes. Un fallback **client-side puro** de `parse_reference` + canonical URL elimina ese cliff.
3. **Edge / serverless** — Cloudflare Workers, Vercel Edge, Deno Deploy: ninguno corre Python. Un endpoint que resuelva referencias bíblicas y devuelva la URL canónica de WOL puede vivir 100% en TS.

El 80% de esos casos depende de exactamente **3 módulos**: `parse_reference`, `WOLClient.get_bible_chapter`, `parsers.article`. El resto del núcleo Python (cache disco, throttler global, telemetría, JWPUB decrypt, EPUB, RAG, agents, MCP, fine-tuning) **no aporta a esos escenarios** y duplicarlo es engineering wasted. Fase 47 hace exactamente el corte mínimo.

## Objetivos (en orden de prioridad)

1. **Port TS funcional de los 3 módulos** con paridad bit-a-bit contra Python sobre 500 golden fixtures.
2. **CI cross-language** que rompe el merge si TS y Python divergen en cualquier fixture.
3. **Distribución npm pública** como `@jw-agent-toolkit/core` (ESM-only, types incluidos).
4. **Source of truth única** para el registro de libros (Python genera JSON, TS consume JSON; no se permite divergencia editorial).

## No-objetivos (boundaries vinculantes)

Líneas que Fase 47 **no** cruza — explícitas para evitar scope creep XL → XXL:

- **No** port de `cache/`, `throttle/`, `telemetry/`, `jwpub/`, `epub/`, `pdf/`, `audio/`, `vision/`. Esas viven en Python y se accedan por REST si JS las necesita.
- **No** port de `jw-rag`, `jw-agents`, `jw-mcp`, `jw-eval`, `jw-finetune`, `jw-gen`. Cero.
- **No** dual ESM+CJS. ESM only — Node ≥18, browsers modernos, Bun, Deno. CJS es legacy y dobla la matriz de testing.
- **No** soporte de `XMLHttpRequest` ni Node ≤16. Usamos `fetch` global.
- **No** crear un paquete `@jw-agent-toolkit/cli-js`, ni `@jw-agent-toolkit/agents-js`. Solo `@jw-agent-toolkit/core`.
- **No** publicar a JSR todavía. Solo npm en esta fase. JSR queda como follow-up trivial.

## Arquitectura

Nuevo workspace member npm. **NO** es un paquete Python — el monorepo pasa a ser polyglot Python + TS, con la frontera explícita.

```
packages/jw-core-js/
├── package.json                  # name "@jw-agent-toolkit/core", v0.1.0, ESM only
├── tsconfig.json
├── tsdown.config.ts              # bundler (ver "Build tool" abajo)
├── vitest.config.ts
├── README.md
├── LICENSE                       # GPL-3.0-only (match Python)
├── src/
│   ├── index.ts                  # re-exports públicos
│   ├── reference.ts              # parse_reference port
│   ├── models.ts                 # BibleRef interface + zod schema
│   ├── languages.ts              # mapping iso → wol_resource/lp_tag/default_bible
│   ├── data/
│   │   └── books.json            # generado por scripts/dump_books_json.py (Python)
│   ├── clients/
│   │   └── wol.ts                # WOLClient (fetch-based, no cache, no throttle)
│   └── parsers/
│       └── article.ts            # parse_article (linkedom-based)
├── tests/
│   ├── reference.test.ts         # Vitest, monolingual edge cases
│   ├── wol.test.ts               # nock-style mock fetch
│   ├── article.test.ts           # fixture HTML → expected Article
│   ├── cross_lang/
│   │   └── parity.test.ts        # consume golden JSON, asserts bit-equal
│   └── fixtures/
│       └── article_snippets/     # HTML pinned snapshots
└── tools/
    └── verify-books-json.ts      # check books.json no editado a mano
```

### Reglas duras de diseño

1. **TS no importa nada de Node-only en runtime de browser**. `fetch` es global. Si necesitamos parsear HTML, usamos `linkedom` (DOM puro JS, sin native deps); **no** `jsdom` (depende de Node) ni `cheerio` (jQuery-style, API divergente). 
2. **`src/data/books.json` jamás se edita a mano**. Se genera desde `packages/jw-core/scripts/dump_books_json.py`. CI verifica equivalencia (ver "Sincronización" abajo).
3. **TS y Python comparten exactamente las mismas fixtures cross-language** (`packages/jw-core/tests/fixtures/cross_lang/*.json`). Ambos lados las leen del mismo directorio.
4. **Tipos exportados con zod schemas** además de TypeScript types — runtime validation viable desde JS sin TS.
5. **Cero side effects en import time**. El registro de libros se lazy-carga solo cuando `parseReference` se invoca.
6. **Errores como tagged unions** (`{ ok: true, value } | { ok: false, error }`) para evitar try/catch ergonomy issues en cliente.

## Los 3 módulos portados

### 1. `parse_reference` (`src/reference.ts`)

Port directo del algoritmo Python actual:

1. Normalizar input (lowercase + strip de combining accents via `String.prototype.normalize('NFD')` + filtro de `\p{M}`).
2. Construir master regex desde `books.json`, alternantes ordenadas longest-first.
3. Lookup en index `key (normalizado, sin espacios) → { bookNum, lang, canonical }`.
4. Devolver `BibleRef | null` (singleton helper) o `BibleRef[]` (parseAll).

**API pública** (igual shape que Python):

```ts
export interface BibleRef {
  bookNum: number;           // 1..66
  bookCanonical: string;     // "John"
  chapter: number;
  verseStart: number | null;
  verseEnd: number | null;
  detectedLanguage: string;  // "en" | "es" | "pt" | ...
  rawMatch: string;
}

export function parseReference(text: string): BibleRef | null;
export function parseAllReferences(text: string): BibleRef[];
export class ReferenceParser {
  constructor();
  parse(text: string): BibleRef[];
  parseOne(text: string): BibleRef | null;
}
```

**Decisión clave — naming convention**: Python usa `snake_case`, TS idiomáticamente `camelCase`. Los **identifiers** son camelCase (`bookNum`, `parseReference`). El **JSON serialization** para cross-lang fixtures usa **`snake_case`** (lo que Python emite por defecto) — el comparator TS aplica un mapper al deserializar. Esto evita pelearse con `pydantic.alias_generators` y mantiene fixtures legibles en ambos lados.

### 2. `WOLClient.get_bible_chapter` (`src/clients/wol.ts`)

Stub mínimo: construye la URL canónica, hace `fetch`, devuelve `{ url, html }`. **No** cache, **no** throttle, **no** telemetry — el caller TS las añade si las necesita (`packages/jw-core/src/jw_core/clients/_polite.py` queda Python-only).

```ts
export interface FetchedDocument {
  url: string;
  html: string;
}

export interface WOLClientOptions {
  fetch?: typeof fetch;         // inject for testing
  userAgent?: string;           // default "jw-agent-toolkit-js/0.1 (+research)"
  timeoutMs?: number;           // default 30000
}

export class WOLClient {
  constructor(options?: WOLClientOptions);
  async fetch(url: string): Promise<string>;
  async getBibleChapter(
    bookNum: number,
    chapter: number,
    options?: { language?: string; publication?: string }
  ): Promise<FetchedDocument>;
}

export class WOLError extends Error {}
```

**URL builder** debe ser **bit-equal** al Python:
`https://wol.jw.org/{iso}/wol/b/{wol_resource}/{lp_tag}/{pub}/{book_num}/{chapter}`. La tabla de `iso → wol_resource/lp_tag/default_bible` vive en `src/languages.ts`, dumpeada también desde Python (ver "Sincronización"). Un fixture cross-lang valida 30 combinaciones de `(language, book, chapter)`.

**Timeout**: implementado con `AbortController` + `setTimeout`. En tests, se inyecta un `fetch` mock que devuelve HTML controlado.

### 3. `parse_article` (`src/parsers/article.ts`)

Port del extractor BeautifulSoup. Uso de [`linkedom`](https://github.com/WebReflection/linkedom) (DOM API puro JS, funciona en browser/Node/Workers, ~70KB minified). API:

```ts
export interface Article {
  title: string;
  paragraphs: string[];
  references: string[];
}

export function parseArticle(html: string): Article;
```

**Selectores y heurística idénticos a Python**:
- title: `h1` → `header h1` → `.pubName` → `<title>` (primer hit no-vacío)
- paragraphs: dentro de `article#article` (fallback `article`, luego `document`), `<p data-pid>` o `id="p*"`
- references: anchors con clase que contiene `b` (palabra suelta)

**Tests cross-lang** sobre un set de ~50 HTML snippets (subset reducido de WOL articles ya pinneados en `packages/jw-core/tests/fixtures/wol_*.html`). Cada snippet alimenta al parser Python y al TS; ambos emiten JSON; el comparator asegura igualdad de `title` + `paragraphs[]` + `references[]` (ordenados).

## Sincronización Python ⇄ TS — el problema más sensible

**Sin disciplina explícita esto degenera en dos sources of truth divergentes en 6 meses.** La política:

### Política #1 — Books como JSON generado, NO duplicado

El registro de libros vive **canónicamente** en `packages/jw-core/src/jw_core/data/books.py` + extensions `books_tier1.py` + `book_locales.py`. Cualquier cambio editorial se hace allí.

Un nuevo script:

```python
# packages/jw-core/scripts/dump_books_json.py
"""Dump the resolved BOOKS registry as JSON for the TS port.

Output: packages/jw-core-js/src/data/books.json
Pre-condition: ruff format clean.
Post-condition: TS workspace can re-bundle.
"""
import json, hashlib
from pathlib import Path
from jw_core.data.books import BOOKS

OUT = Path("packages/jw-core-js/src/data/books.json")
META = Path("packages/jw-core-js/src/data/books.meta.json")

def main() -> None:
    payload = sorted(BOOKS, key=lambda b: b["num"])
    serialized = json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True)
    OUT.write_text(serialized + "\n", encoding="utf-8")
    digest = hashlib.sha256(serialized.encode("utf-8")).hexdigest()
    META.write_text(json.dumps({"sha256": digest, "count": len(payload)}, indent=2) + "\n")
```

Análogamente `dump_languages_json.py` exporta el mapping `iso → wol_resource/lp_tag/default_bible`.

**CI job `books-json-fresh`**:
```bash
uv run python packages/jw-core/scripts/dump_books_json.py
git diff --exit-code packages/jw-core-js/src/data/books.json packages/jw-core-js/src/data/books.meta.json
```

Si el script produce un diff, CI rompe con mensaje explícito: "books.json drift detected — regenerate via `uv run python packages/jw-core/scripts/dump_books_json.py` and commit".

### Política #2 — Cross-language parity test sobre 500 fixtures

Las fixtures viven en **un** directorio compartido: `packages/jw-core/tests/fixtures/cross_lang/`:

```
cross_lang/
├── parse_reference/
│   ├── 001_juan_3_16_es.json
│   ├── 002_john_3_16_en_short.json
│   ├── 003_joao_3_16_pt.json
│   ├── ...
│   └── 500_edge_unicode_punct.json
├── wol_url/
│   └── ...
└── article/
    ├── 001_w23-spanish.html
    ├── 001_w23-spanish.expected.json
    └── ...
```

Cada fixture `parse_reference/NNN_*.json`:

```json
{
  "id": "001_juan_3_16_es",
  "input": "Hablemos sobre Juan 3:16 hoy",
  "expected": {
    "book_num": 43,
    "book_canonical": "John",
    "chapter": 3,
    "verse_start": 16,
    "verse_end": null,
    "detected_language": "es",
    "raw_match": "juan 3:16"
  }
}
```

Bootstrap inicial: **500 casos generados semi-automáticamente** desde los tests Python existentes (`test_reference_parser.py`) + expansión multi-lang programática (30 libros × 5 chapters × 3 langs ≈ 450) + 50 edge cases hand-curated (unicode, dots, hyphens, paréntesis, falsos positivos como "Juan habló").

**Python side** (`packages/jw-core/tests/test_cross_lang_parity.py`):

```python
@pytest.mark.parametrize("fixture", _load_fixtures("cross_lang/parse_reference"))
def test_python_parse_reference_matches_fixture(fixture):
    ref = parse_reference(fixture["input"])
    actual = ref.model_dump() if ref else None
    assert actual == fixture["expected"], (
        f"Fixture {fixture['id']}: Python output diverged from expected. "
        f"If this is intentional, regenerate fixtures via "
        f"`uv run python packages/jw-core/scripts/regenerate_cross_lang_fixtures.py`"
    )
```

**TS side** (`packages/jw-core-js/tests/cross_lang/parity.test.ts`):

```ts
import { describe, it, expect } from 'vitest';
import { parseReference } from '../../src/reference';
import { loadFixtures } from './_loader';

describe('parse_reference parity', () => {
  for (const fx of loadFixtures('parse_reference')) {
    it(fx.id, () => {
      const ref = parseReference(fx.input);
      const actual = ref ? toSnakeCase(ref) : null;
      expect(actual).toEqual(fx.expected);
    });
  }
});
```

**CI job `cross-lang-parity`** corre ambas suites; **ambas** deben pasar. Si solo Python pasa, TS está roto. Si solo TS pasa, alguien metió un fixture nuevo sin regenerar el expected — la fixture es la verdad.

### Política #3 — Cuando Python evoluciona

Cualquier PR que toque `parse_reference`, `WOLClient.get_bible_chapter`, `parse_article` o `BOOKS` debe:

1. Actualizar el código Python.
2. Regenerar `books.json` si aplica (`make dump-shared-data` lo automatiza).
3. Actualizar las fixtures cross-lang afectadas (`make regen-cross-lang-fixtures` con confirmación interactiva).
4. Actualizar el TS port en el mismo PR (o abrir issue link-back en menos de 1 sprint si el cambio es complejo; CI bloquea el merge hasta que el TS coincida).

La regla operacional: **Python lidera, TS sigue dentro del mismo PR**. No se permite que TS drifte del Python por más de un commit a `main`.

## Stack técnico

### Build tool: `tsdown` (no Vite, no Rollup, no Jest)

Decisiones:

| Concern | Elección | Por qué |
|---|---|---|
| Bundler | **tsdown** (Rolldown bajo el capó) | Built-in TS, dual ESM emission opcional, declaraciones `.d.ts` automáticas, minimal config. Más rápido que tsup. |
| Test runner | **Vitest** | Native ESM, native TS, compatible con Vite ecosystem, parallelización gratis, snapshot inline. Jest queda descartado por: friction con ESM, CJS-first, mocking ad-hoc menos ergonómico. |
| Lint/format | **Biome** | Single binary, sin plugins JS-ecosystem hell. (Alt: eslint + prettier; Biome gana por velocidad y zero-config.) |
| Type checker | `tsc --noEmit` (estricto) | Estándar. `strict: true`, `noUncheckedIndexedAccess: true`. |
| Node version | ≥18 | Para `fetch` global y top-level await. |
| TS version | 5.6+ | `using` declarations, `unknown` improvements, `verbatimModuleSyntax`. |

### `package.json` (skeleton)

```jsonc
{
  "name": "@jw-agent-toolkit/core",
  "version": "0.1.0",
  "description": "Bible reference parser, WOL HTML client, and article parser — TypeScript port of jw-core's 3 essential modules.",
  "type": "module",
  "main": "./dist/index.js",
  "types": "./dist/index.d.ts",
  "exports": {
    ".": { "import": "./dist/index.js", "types": "./dist/index.d.ts" },
    "./reference": { "import": "./dist/reference.js", "types": "./dist/reference.d.ts" },
    "./clients/wol": { "import": "./dist/clients/wol.js", "types": "./dist/clients/wol.d.ts" },
    "./parsers/article": { "import": "./dist/parsers/article.js", "types": "./dist/parsers/article.d.ts" }
  },
  "sideEffects": false,
  "files": ["dist", "src", "LICENSE", "README.md"],
  "scripts": {
    "build": "tsdown",
    "test": "vitest run",
    "test:watch": "vitest",
    "lint": "biome check src tests",
    "lint:fix": "biome check --write src tests",
    "typecheck": "tsc --noEmit",
    "verify": "pnpm run lint && pnpm run typecheck && pnpm run test && pnpm run build"
  },
  "license": "GPL-3.0-only",
  "repository": { "type": "git", "url": "https://github.com/eliascipre/jw-agent-toolkit", "directory": "packages/jw-core-js" },
  "engines": { "node": ">=18" },
  "dependencies": {
    "linkedom": "^0.18.0",
    "zod": "^3.23.0"
  },
  "devDependencies": {
    "@biomejs/biome": "^1.9.0",
    "@types/node": "^22.10.0",
    "tsdown": "^0.6.0",
    "typescript": "^5.6.0",
    "vitest": "^2.1.0"
  }
}
```

### Workspace integration

Raíz del repo gana `pnpm-workspace.yaml`:
```yaml
packages:
  - 'packages/jw-core-js'
  - 'apps/obsidian-jw-bridge'
  - 'apps/desktop'
```

Esto unifica los workspaces TS existentes. `obsidian-jw-bridge` y `desktop` siguen usando lo que ya usan (cada uno con su tooling); el monorepo solo gana coordinación de versiones y `pnpm install` único.

**Por qué pnpm y no npm**: workspace nativo más estricto, content-addressable store ahorra disco, `pnpm -r` ejecuta en cada paquete trivialmente. Si en el futuro hubiera resistencia, fallback a `npm workspaces` no rompe el modelo.

## Decisión de licencia: GPL-3.0-only

El paquete Python es GPL-3.0-only. Mantenerlo igual en npm:

- **Coherencia legal** — un fork puede compilar Python y JS bajo la misma licencia sin friction.
- **Compatible con npm** — npm acepta GPL-3.0; aparece en la página del paquete y `npm view` lo expone.
- **No bloquea adopción**: las apps que solo **consumen** la librería pueden ser cualquier licencia. GPL solo obliga si se redistribuye **modificada**. Para librerías de **datos doctrinales** + parser, esa cláusula es deseable: cambios al parser de referencias bíblicas vuelven al ecosistema.

**MIT descartado** porque:
- Permite que un fork comercial cierre el código de toda la frontera JS sin contribuir back.
- Asimetría con el resto del repo Python (mixed-licensing en un mismo monorepo invita malentendidos).

**LGPL** considerada como middle ground (permite linking sin contagio); descartada por simplicity: el toolkit es "research + community", no infra de terceros que vaya a empotrarse en código propietario crítico. GPL es el default cultural del proyecto JW (cf. Obsidian plugins, JWLibrary export tools).

Archivo `packages/jw-core-js/LICENSE` = copia literal del GPL-3.0 ya presente en `LICENSE` raíz.

## Ownership del scope npm `@jw-agent-toolkit/*`

Antes de publicar `@jw-agent-toolkit/core` hay que:

1. **Registrar el scope** en npm bajo el usuario `eliascipre` (o crear org `jw-agent-toolkit` si conviene). Org es preferible: permite múltiples maintainers sin compartir credenciales.
2. **Reservar el nombre `@jw-agent-toolkit/core`** publicando un `v0.0.1` con README only en cuanto el scope exista — evita squatting.
3. Documentar en `docs/publishing/npm.md` el flujo: `pnpm version`, `pnpm build`, `pnpm publish --access public`, GPG-signed git tag.
4. CI workflow `publish-npm-on-tag.yml` que dispara solo en tags `jw-core-js@v*`. Token `NPM_TOKEN` en GitHub secrets. **No** auto-publish en cada merge a `main`.

**SemVer policy**:
- `v0.x.y` durante toda la Fase 47 (API en construcción).
- `v1.0.0` solo cuando: ≥3 meses sin breaking change + ≥1000 fixtures parity green + adopción real (Fase 48 browser-ext usa el paquete).
- Pre-1.0 cualquier change al BibleRef shape rompe minor; post-1.0 rompe major.

## Modelos compartidos

`src/models.ts`:

```ts
import { z } from 'zod';

export const BibleRefSchema = z.object({
  bookNum: z.number().int().min(1).max(66),
  bookCanonical: z.string(),
  chapter: z.number().int().min(1),
  verseStart: z.number().int().min(1).nullable(),
  verseEnd: z.number().int().min(1).nullable(),
  detectedLanguage: z.string(),
  rawMatch: z.string(),
});

export type BibleRef = z.infer<typeof BibleRefSchema>;

export const FetchedDocumentSchema = z.object({
  url: z.string().url(),
  html: z.string(),
});
export type FetchedDocument = z.infer<typeof FetchedDocumentSchema>;

export const ArticleSchema = z.object({
  title: z.string(),
  paragraphs: z.array(z.string()),
  references: z.array(z.string()),
});
export type Article = z.infer<typeof ArticleSchema>;
```

Las funciones públicas devuelven el tipo TS directamente; el schema queda disponible para usuarios JS o validación runtime en boundaries (REST handlers, etc.).

## CI: el job `cross-lang-parity`

Nuevo workflow `.github/workflows/cross-lang.yml`:

```yaml
name: cross-lang
on: [push, pull_request]

jobs:
  parity:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with: { node-version: 20 }
      - uses: pnpm/action-setup@v4
        with: { version: 9 }
      - uses: astral-sh/setup-uv@v3
      - run: uv sync --all-packages
      - run: pnpm -F @jw-agent-toolkit/core install --frozen-lockfile

      # Verify shared data files are fresh
      - name: Books JSON up-to-date
        run: |
          uv run python packages/jw-core/scripts/dump_books_json.py
          uv run python packages/jw-core/scripts/dump_languages_json.py
          git diff --exit-code packages/jw-core-js/src/data/ \
            || (echo "::error::Shared data drift; regenerate via make dump-shared-data" && exit 1)

      # Python parity tests
      - name: Python parity
        run: .venv/bin/python -m pytest packages/jw-core/tests/test_cross_lang_parity.py -v

      # TS parity tests
      - name: TS parity
        working-directory: packages/jw-core-js
        run: pnpm test -- tests/cross_lang/

      # Optional: typecheck + build
      - run: pnpm -F @jw-agent-toolkit/core run typecheck
      - run: pnpm -F @jw-agent-toolkit/core run build
```

Tiempo estimado: ~90s. No introduce flakiness — todo offline, fixtures pinned.

## Integración con apps existentes

### `apps/obsidian-jw-bridge`

Hoy: consume REST API local. Tras Fase 47, opt-in: el plugin puede resolver `parse_reference` **sin red** vía `@jw-agent-toolkit/core` para la action "Insert link de versículo". Mejora UX (instantáneo) y reduce dependencia del REST corriendo.

Cambio: añadir `"@jw-agent-toolkit/core": "workspace:*"` a `obsidian-jw-bridge/package.json`. Migración opcional — Fase 47 no la fuerza; Fase 48 sí.

### `apps/desktop`

Igual patrón. La validación de URLs antes de fetchar puede ser client-side TS.

### Fase 48 (`wol-browser-ext`)

Aquí es donde el TS port cobra valor: la extensión inyecta UI en `wol.jw.org`. Cuando el usuario hace right-click en "Juan 3:16", la extension puede:

1. **Sin backend local**: `parseReference("Juan 3:16")` → BibleRef → construye `wolUrl()` → muestra link curado client-side.
2. **Con backend local** (cuando está corriendo): añade los botones avanzados (Explicar, Cross-refs).

El **fallback graceful** es lo que vuelve la extension realmente usable.

## Tests del propio paquete TS

Más allá de los cross-lang, `packages/jw-core-js/tests/` contiene:

| Test | Cobertura |
|---|---|
| `reference.test.ts` | Singleton helper, parseAll, edge cases TS-only (Unicode NFC vs NFD), error handling de `verseStart > verseEnd` |
| `models.test.ts` | Zod schemas rechazan inputs malformados; `BibleRefSchema.safeParse` con tagged result |
| `languages.test.ts` | 30 combinaciones de URL building; default_bible por idioma |
| `wol.test.ts` | Mock `fetch`, AbortController timeout, error mapping (`HTTPError` → `WOLError`) |
| `article.test.ts` | 10 HTML fixtures locales, no cross-lang, foco en linkedom quirks |
| `cross_lang/parity.test.ts` | El bloque grande — 500 fixtures parse_reference + 30 wol_url + 50 article |

Cobertura objetivo: **≥95% líneas** medido por `vitest --coverage` (c8 backend).

## Riesgos y mitigaciones

| # | Riesgo | Mitigación |
|---|---|---|
| 1 | Regex Python (`re`) y JS divergen en Unicode/word-boundary | Tests dedicados con `\b` casos límite (e.g. "Juan-Pedro"); ambos motores con `IGNORECASE` y normalización NFD pre-match idéntica |
| 2 | `books.json` drift por edit manual | CI job `books-json-fresh` + comment header en el JSON: "GENERATED FILE — do not edit; regenerate via dump_books_json.py" + check `*.meta.json` con sha256 |
| 3 | TS evoluciona sin update Python (o viceversa) | `cross-lang-parity` job es bloqueante en PR; CODEOWNERS marca ambos directorios |
| 4 | linkedom comportamiento difiere de lxml en HTML malformado | Snapshots WOL HTML pinned como fixtures; 10 casos con malformed HTML cubiertos en ambos lados |
| 5 | npm scope `@jw-agent-toolkit/*` squatted antes de publicar | Reservar y publicar `v0.0.1` placeholder en Sprint 1 antes de empezar el desarrollo serio |
| 6 | Adopción cero | Métrica honesta — Fase 48 será el primer consumidor; sin Fase 48 corriendo, retraer publicación pública |
| 7 | Mantener fixtures en sync es trabajo manual | Script `regenerate_cross_lang_fixtures.py` re-genera batch desde inputs declarados; humano solo declara `input + expected` semánticamente |
| 8 | Bundle size explota | Budget hard: gzipped `dist/index.js` ≤ 25KB (parse_reference + models). WOL client +5KB. Article parser (linkedom) +30KB. Total ≤ 60KB gzipped. CI assertion vía size-limit |
| 9 | Python 3.13 `unicodedata` vs JS `String.prototype.normalize` diferencias edge | Fixture explícita con caracteres compuestos raros (ñ, ç, ã, ü); divergencia ≥1 char = fail |
| 10 | TypeScript versions futuras rompen estricto | Versionar `typescript` en devDeps explícito; CI corre `tsc` en cada PR |

## Métricas de éxito de la fase

- ✅ `pnpm -F @jw-agent-toolkit/core verify` corre en <30s local.
- ✅ Cross-lang CI job pasa con 500 fixtures parse_reference + 30 wol_url + 50 article, **100% match**.
- ✅ Bundle gzipped total ≤60KB, `index.js` ≤25KB.
- ✅ `@jw-agent-toolkit/core@0.1.0` publicado en npm con README + LICENSE GPL-3.0-only.
- ✅ `apps/obsidian-jw-bridge` puede consumir el paquete vía `workspace:*` sin breaking change.
- ✅ Documentado en `docs/guias/typescript-port.md` (cómo se sincroniza, cómo regenerar fixtures, cómo se publica).
- ✅ Sin regresiones en los 1984 tests Python existentes.

## Pendientes explícitos (post-Fase 47)

- Publicar a JSR (`@jw-agent-toolkit/core` en jsr.io) — trivial follow-up.
- Port de `daily_text` parser y `bible_chapter` parser — Fase futura cuando haya demanda real.
- Port de `JwpubReader` — improbable (binario + crypto + sqlite; el coste es alto y el caso de uso JS es nicho).
- Wrapper opcional para Node con cache disco + throttle — paquete separado `@jw-agent-toolkit/core-node`, no parte de Fase 47.
- Sync 2-way: actualmente Python lidera. Si en el futuro emerge un módulo nuevo en TS primero (improbable), formalizar política reversa.

## Cómo verificar al cerrar

```bash
# 1. Regenerar shared data
uv run python packages/jw-core/scripts/dump_books_json.py
uv run python packages/jw-core/scripts/dump_languages_json.py

# 2. Build + test TS
cd packages/jw-core-js
pnpm install
pnpm run verify

# 3. Cross-lang parity (Python side)
.venv/bin/python -m pytest packages/jw-core/tests/test_cross_lang_parity.py -v

# 4. Bundle size budget
pnpm -F @jw-agent-toolkit/core exec size-limit

# 5. Dry-run publish (no upload)
pnpm -F @jw-agent-toolkit/core publish --dry-run --access public
```

## Plan de implementación (alto nivel)

Spec hijo: `docs/superpowers/plans/2026-05-31-fase-47-jw-core-js-minimal-plan.md` (a escribir tras aprobar este spec).

Pasos cronológicos (~6-8 semanas, 1 dev):

1. **Sprint 1** — Reservar scope npm; scaffold `packages/jw-core-js/` (package.json, tsconfig, tsdown, vitest, biome); CI workflow esqueleto.
2. **Sprint 1-2** — Scripts `dump_books_json.py` + `dump_languages_json.py`; primer JSON commiteado; CI job `books-json-fresh` verde.
3. **Sprint 2** — Port `parse_reference` + `models.ts` + zod schemas; 50 tests TS-only.
4. **Sprint 3** — Bootstrap fixtures cross-lang (500 parse_reference); tests Python parametrizados + tests TS parity; CI job `cross-lang-parity` verde.
5. **Sprint 4** — Port `WOLClient` con mocked fetch; 30 fixtures cross-lang de wol_url.
6. **Sprint 5** — Port `parse_article` con linkedom; 50 fixtures cross-lang HTML.
7. **Sprint 6** — Polish: README extenso, ejemplos de uso (browser, Node, Workers, Deno), `docs/guias/typescript-port.md`, audit 1:1 en `docs/VISION_AUDIT.md`.
8. **Sprint 7** — Publicar `v0.1.0` a npm; smoke test desde `obsidian-jw-bridge` consumiendo `workspace:*`.
9. **Sprint 8** — Buffer + bug fixes + alinear con Fase 48 si arranca paralelo.

Cada sprint con su PR + tests + sin regresiones en los 1984 tests Python existentes. CI cross-lang debe estar verde en cada merge a `main`.
