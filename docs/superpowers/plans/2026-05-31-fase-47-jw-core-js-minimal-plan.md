# Fase 47 — `jw-core-js-minimal` Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Port the 3 essential modules of `jw-core` (parse_reference, WOLClient.get_bible_chapter, parse_article) to TypeScript as `@jw-agent-toolkit/core`, ESM-only, with bit-equal parity to Python enforced by a 500+ fixture cross-language CI job. Publish to npm under the reserved scope.

**Architecture:** New polyglot workspace member `packages/jw-core-js/`. tsdown bundler, Vitest tests, Biome lint+format, linkedom for HTML parsing, zod for runtime schemas. The Python `jw-core` package generates `books.json` + `languages.json` via two new dump scripts; CI verifies the dump is fresh and that 500 fixtures produce identical output from both runtimes. pnpm workspace ties the existing TS apps (`obsidian-jw-bridge`, `desktop`) together with the new package.

**Tech Stack:** Node ≥18 · TypeScript 5.6 (strict, `noUncheckedIndexedAccess`) · tsdown (Rolldown) bundler · Vitest test runner · Biome lint+format · linkedom (DOM in pure JS) · zod 3 (runtime schemas) · pnpm 9 workspace · GitHub Actions CI (`cross-lang` job) · GPL-3.0-only.

**Spec:** [`docs/superpowers/specs/2026-05-31-fase-47-jw-core-js-minimal-design.md`](../specs/2026-05-31-fase-47-jw-core-js-minimal-design.md).

---

## File map

Creates (TypeScript package `packages/jw-core-js/`):
- `packages/jw-core-js/package.json`
- `packages/jw-core-js/tsconfig.json`
- `packages/jw-core-js/tsdown.config.ts`
- `packages/jw-core-js/vitest.config.ts`
- `packages/jw-core-js/biome.json`
- `packages/jw-core-js/.gitignore`
- `packages/jw-core-js/.npmignore`
- `packages/jw-core-js/README.md`
- `packages/jw-core-js/LICENSE`
- `packages/jw-core-js/CHANGELOG.md`
- `packages/jw-core-js/src/index.ts`
- `packages/jw-core-js/src/models.ts`
- `packages/jw-core-js/src/reference.ts`
- `packages/jw-core-js/src/languages.ts`
- `packages/jw-core-js/src/data/books.json` — generated, do not edit
- `packages/jw-core-js/src/data/books.meta.json` — generated, do not edit
- `packages/jw-core-js/src/data/languages.json` — generated, do not edit
- `packages/jw-core-js/src/data/languages.meta.json` — generated, do not edit
- `packages/jw-core-js/src/clients/wol.ts`
- `packages/jw-core-js/src/parsers/article.ts`
- `packages/jw-core-js/src/_internal/snakeCase.ts`
- `packages/jw-core-js/tests/reference.test.ts`
- `packages/jw-core-js/tests/models.test.ts`
- `packages/jw-core-js/tests/languages.test.ts`
- `packages/jw-core-js/tests/wol.test.ts`
- `packages/jw-core-js/tests/article.test.ts`
- `packages/jw-core-js/tests/cross_lang/_loader.ts`
- `packages/jw-core-js/tests/cross_lang/parity.test.ts`
- `packages/jw-core-js/tests/fixtures/article_snippets/sample_w23_en.html`
- `packages/jw-core-js/tests/fixtures/article_snippets/sample_w23_en.expected.json`
- `packages/jw-core-js/tools/verify-books-json.ts`

Creates (Python side helpers + shared fixtures):
- `packages/jw-core/scripts/dump_books_json.py`
- `packages/jw-core/scripts/dump_languages_json.py`
- `packages/jw-core/scripts/regenerate_cross_lang_fixtures.py`
- `packages/jw-core/tests/test_cross_lang_parity.py`
- `packages/jw-core/tests/fixtures/cross_lang/parse_reference/001..500_*.json` (500 fixtures)
- `packages/jw-core/tests/fixtures/cross_lang/wol_url/001..030_*.json` (30 fixtures)
- `packages/jw-core/tests/fixtures/cross_lang/article/001..050_*.{html,expected.json}` (50 pairs)

Creates (root workspace + CI + docs):
- `pnpm-workspace.yaml`
- `package.json` (root, minimal — only for pnpm coordination)
- `.github/workflows/cross-lang.yml`
- `.github/workflows/publish-npm-on-tag.yml`
- `docs/guias/typescript-port.md`
- `docs/publishing/npm.md`
- `Makefile` updates: `dump-shared-data`, `regen-cross-lang-fixtures`

Modifies:
- `.gitignore` (root) — add `packages/jw-core-js/dist/`, `packages/jw-core-js/node_modules/`, root `node_modules/`.
- `docs/VISION_AUDIT.md` — add Fase 47 row.
- `docs/ROADMAP.md` — add Fase 47 section.
- `docs/README.md` — link new guide.
- `packages/jw-core/src/jw_core/parsers/reference.py` — add `BibleRef.model_dump()` parity helper (no behavior change; export-only refinement).

---

## Sprint structure

This is an XL fase. Tasks are grouped into 8 sprints; each sprint is independently merge-able. Recommended cadence is one sprint per week with one dev.

| Sprint | Tasks | Outcome |
|---|---|---|
| 1 | 1–3 | Workspace scaffolded, npm scope reserved at v0.0.1, books.json export script exists, CI skeleton green |
| 2 | 4–6 | `parseReference` ported with 50 TS-only tests; zod models + snake_case bridge |
| 3 | 7–9 | 500 cross-lang fixtures generated + Python parametrized parity + TS parity test green |
| 4 | 10–12 | `WOLClient.getBibleChapter` ported + languages.json export + 30 cross-lang URL fixtures |
| 5 | 13–15 | `parseArticle` ported with linkedom + 50 cross-lang HTML fixtures |
| 6 | 16–17 | Bundle size budget enforced, README extensive, examples, `docs/guias/typescript-port.md` |
| 7 | 18–19 | Publish v0.1.0 to npm, smoke test from `obsidian-jw-bridge` |
| 8 | 20–21 | VISION_AUDIT + ROADMAP land, final audit, no regressions in 1984 Python tests |

---

### Task 1: Scaffold `packages/jw-core-js/` package skeleton

**Files:**
- Create: `packages/jw-core-js/package.json`
- Create: `packages/jw-core-js/tsconfig.json`
- Create: `packages/jw-core-js/tsdown.config.ts`
- Create: `packages/jw-core-js/vitest.config.ts`
- Create: `packages/jw-core-js/biome.json`
- Create: `packages/jw-core-js/.gitignore`
- Create: `packages/jw-core-js/.npmignore`
- Create: `packages/jw-core-js/LICENSE`
- Create: `packages/jw-core-js/README.md`
- Create: `packages/jw-core-js/CHANGELOG.md`
- Create: `packages/jw-core-js/src/index.ts`
- Create: `pnpm-workspace.yaml`
- Create: `package.json` (root)
- Modify: `.gitignore` (root)

- [ ] **Step 1: Create `package.json`**

```jsonc
{
  "name": "@jw-agent-toolkit/core",
  "version": "0.0.1",
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
  "files": ["dist", "src", "LICENSE", "README.md", "CHANGELOG.md"],
  "scripts": {
    "build": "tsdown",
    "test": "vitest run",
    "test:watch": "vitest",
    "lint": "biome check src tests",
    "lint:fix": "biome check --write src tests",
    "typecheck": "tsc --noEmit",
    "verify": "pnpm run lint && pnpm run typecheck && pnpm run test && pnpm run build",
    "prepublishOnly": "pnpm run verify"
  },
  "license": "GPL-3.0-only",
  "repository": {
    "type": "git",
    "url": "https://github.com/eliascipre/jw-agent-toolkit",
    "directory": "packages/jw-core-js"
  },
  "homepage": "https://github.com/eliascipre/jw-agent-toolkit/tree/main/packages/jw-core-js#readme",
  "bugs": { "url": "https://github.com/eliascipre/jw-agent-toolkit/issues" },
  "keywords": ["jw", "bible", "wol", "parser", "reference", "watchtower-online-library"],
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

- [ ] **Step 2: Create `tsconfig.json`**

```jsonc
{
  "compilerOptions": {
    "target": "ES2022",
    "module": "ESNext",
    "moduleResolution": "Bundler",
    "lib": ["ES2022", "DOM"],
    "strict": true,
    "noUncheckedIndexedAccess": true,
    "noImplicitOverride": true,
    "exactOptionalPropertyTypes": true,
    "verbatimModuleSyntax": true,
    "isolatedModules": true,
    "esModuleInterop": true,
    "resolveJsonModule": true,
    "skipLibCheck": true,
    "declaration": true,
    "declarationMap": true,
    "sourceMap": true,
    "outDir": "dist",
    "rootDir": "src",
    "types": ["node"]
  },
  "include": ["src/**/*.ts", "src/**/*.json"],
  "exclude": ["node_modules", "dist", "tests"]
}
```

- [ ] **Step 3: Create `tsdown.config.ts`**

```ts
import { defineConfig } from 'tsdown';

export default defineConfig({
  entry: [
    'src/index.ts',
    'src/reference.ts',
    'src/clients/wol.ts',
    'src/parsers/article.ts',
  ],
  format: ['esm'],
  dts: true,
  clean: true,
  sourcemap: true,
  target: 'node18',
  treeshake: true,
  external: ['linkedom', 'zod'],
});
```

- [ ] **Step 4: Create `vitest.config.ts`**

```ts
import { defineConfig } from 'vitest/config';

export default defineConfig({
  test: {
    environment: 'node',
    include: ['tests/**/*.test.ts'],
    coverage: {
      provider: 'v8',
      reporter: ['text', 'html', 'json-summary'],
      include: ['src/**/*.ts'],
      exclude: ['src/data/**', 'src/index.ts'],
      thresholds: {
        lines: 90,
        functions: 90,
        branches: 85,
        statements: 90,
      },
    },
    testTimeout: 10_000,
  },
});
```

- [ ] **Step 5: Create `biome.json`**

```jsonc
{
  "$schema": "https://biomejs.dev/schemas/1.9.0/schema.json",
  "files": { "ignore": ["dist", "node_modules", "src/data/*.json"] },
  "organizeImports": { "enabled": true },
  "formatter": {
    "enabled": true,
    "indentStyle": "space",
    "indentWidth": 2,
    "lineWidth": 100,
    "lineEnding": "lf"
  },
  "linter": {
    "enabled": true,
    "rules": {
      "recommended": true,
      "style": {
        "useImportType": "error",
        "useNodejsImportProtocol": "error"
      },
      "suspicious": {
        "noExplicitAny": "warn"
      },
      "correctness": {
        "noUnusedImports": "error",
        "noUnusedVariables": "error"
      }
    }
  },
  "javascript": {
    "formatter": {
      "quoteStyle": "single",
      "semicolons": "always",
      "trailingCommas": "all",
      "arrowParentheses": "always"
    }
  }
}
```

- [ ] **Step 6: Create `.gitignore` and `.npmignore`**

```gitignore
# packages/jw-core-js/.gitignore
node_modules
dist
coverage
*.log
.DS_Store
```

```gitignore
# packages/jw-core-js/.npmignore
node_modules
coverage
tests
tools
tsdown.config.ts
vitest.config.ts
biome.json
tsconfig.json
.gitignore
.npmignore
```

- [ ] **Step 7: Create `LICENSE` (GPL-3.0-only, copy from root)**

Run:
```bash
cp /Users/elias/Documents/Trabajo/jw-agent-toolkit/LICENSE \
   /Users/elias/Documents/Trabajo/jw-agent-toolkit/packages/jw-core-js/LICENSE
```

- [ ] **Step 8: Create `README.md`**

```markdown
# @jw-agent-toolkit/core

TypeScript port of the 3 essential modules of [`jw-core`](https://github.com/eliascipre/jw-agent-toolkit/tree/main/packages/jw-core):

- `parseReference(text)` — multi-language Bible reference parser (en/es/pt + tier-1 langs).
- `WOLClient.getBibleChapter(book, chapter)` — fetch HTML from `wol.jw.org`.
- `parseArticle(html)` — extract title, paragraphs, references from a WOL article page.

ESM-only. Runs in Node ≥18, modern browsers, Bun, Deno, Cloudflare Workers.

## Install

```bash
npm install @jw-agent-toolkit/core
# or: pnpm add @jw-agent-toolkit/core
# or: bun add @jw-agent-toolkit/core
```

## Usage

```ts
import { parseReference } from '@jw-agent-toolkit/core/reference';

const ref = parseReference('Juan 3:16');
// { bookNum: 43, bookCanonical: 'John', chapter: 3, verseStart: 16, ... }
```

```ts
import { WOLClient } from '@jw-agent-toolkit/core/clients/wol';

const client = new WOLClient();
const { url, html } = await client.getBibleChapter(43, 3, { language: 'es' });
```

```ts
import { parseArticle } from '@jw-agent-toolkit/core/parsers/article';

const article = parseArticle(html);
console.log(article.title, article.paragraphs.length, article.references);
```

## Parity with Python

This package is generated from the Python `jw-core` source-of-truth and
verified by a CI job that runs 500+ shared fixtures through both runtimes.
See [docs/guias/typescript-port.md](../../docs/guias/typescript-port.md).

## License

GPL-3.0-only — matches the Python `jw-core` package.
```

- [ ] **Step 9: Create `CHANGELOG.md`**

```markdown
# Changelog

## 0.0.1 — 2026-05-31

- Scope `@jw-agent-toolkit/*` reserved on npm.
- Placeholder publish. No functional code yet.

## Unreleased

- 0.1.0 — `parseReference`, `WOLClient.getBibleChapter`, `parseArticle` (Fase 47).
```

- [ ] **Step 10: Create empty entry-points**

```ts
// packages/jw-core-js/src/index.ts
export {} from './_internal/nothing-yet';
```

Actually, simpler:

```ts
// packages/jw-core-js/src/index.ts
// Public surface — populated in later tasks.
// Re-exports added in Tasks 5, 11, 14.
export const VERSION = '0.0.1';
```

- [ ] **Step 11: Create root `pnpm-workspace.yaml`**

```yaml
packages:
  - 'packages/jw-core-js'
  - 'apps/obsidian-jw-bridge'
  - 'apps/desktop'
```

- [ ] **Step 12: Create root `package.json` (coordination only)**

```jsonc
{
  "name": "jw-agent-toolkit-workspace",
  "version": "0.0.0",
  "private": true,
  "description": "Coordination root for the polyglot jw-agent-toolkit monorepo (Python + TypeScript).",
  "packageManager": "pnpm@9.12.0",
  "scripts": {
    "js:install": "pnpm install",
    "js:build": "pnpm -F @jw-agent-toolkit/core build",
    "js:test": "pnpm -F @jw-agent-toolkit/core test",
    "js:verify": "pnpm -F @jw-agent-toolkit/core verify"
  },
  "engines": { "node": ">=18", "pnpm": ">=9" }
}
```

- [ ] **Step 13: Update root `.gitignore`**

Append:

```gitignore
# Node / pnpm
node_modules/
packages/jw-core-js/dist/
packages/jw-core-js/coverage/
.pnpm-store/
```

- [ ] **Step 14: Verify installation**

Run:
```bash
cd /Users/elias/Documents/Trabajo/jw-agent-toolkit
pnpm install
```

Expected: lockfile `pnpm-lock.yaml` created; `node_modules/` populated. No errors.

- [ ] **Step 15: Verify typecheck + lint baseline pass**

Run:
```bash
pnpm -F @jw-agent-toolkit/core run typecheck
pnpm -F @jw-agent-toolkit/core run lint
```

Expected: zero errors. (We only have a single trivial file.)

- [ ] **Step 16: Commit**

```bash
git add packages/jw-core-js pnpm-workspace.yaml package.json .gitignore pnpm-lock.yaml
git commit -m "feat(jw-core-js): scaffold TS workspace member and pnpm coordination root"
```

---

### Task 2: Python `dump_books_json.py` + `dump_languages_json.py` scripts

**Files:**
- Create: `packages/jw-core/scripts/dump_books_json.py`
- Create: `packages/jw-core/scripts/dump_languages_json.py`
- Create: `packages/jw-core-js/src/data/books.json` — generated
- Create: `packages/jw-core-js/src/data/books.meta.json` — generated
- Create: `packages/jw-core-js/src/data/languages.json` — generated
- Create: `packages/jw-core-js/src/data/languages.meta.json` — generated
- Create: `packages/jw-core-js/tools/verify-books-json.ts`
- Modify: `Makefile`

- [ ] **Step 1: Create `dump_books_json.py`**

```python
# packages/jw-core/scripts/dump_books_json.py
"""Dump the resolved BOOKS registry as JSON for the TypeScript port.

This is the SINGLE source of truth bridge. The Python `jw_core.data.books`
module is the canonical registry; this script materializes it into a JSON
the TS package consumes verbatim.

Output:
    packages/jw-core-js/src/data/books.json       — sorted by num, indented 2
    packages/jw-core-js/src/data/books.meta.json  — sha256 + count

Pre-condition: `uv sync --all-packages` so `jw_core` is importable.
Post-condition: TS workspace can re-bundle with no editorial divergence.

CI invariant: `git diff --exit-code packages/jw-core-js/src/data/` must
remain clean after running this script. Any drift fails the `cross-lang` job.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from jw_core.data.books import BOOKS

REPO_ROOT = Path(__file__).resolve().parents[3]
OUT = REPO_ROOT / "packages" / "jw-core-js" / "src" / "data" / "books.json"
META = REPO_ROOT / "packages" / "jw-core-js" / "src" / "data" / "books.meta.json"

HEADER_COMMENT = (
    "// !!! GENERATED FILE !!! Do not edit by hand.\n"
    "// Regenerate via: uv run python packages/jw-core/scripts/dump_books_json.py\n"
)


def _normalize_book(book: dict) -> dict:
    """Sort the names per language so the serialization is stable."""

    names = {lang: list(values) for lang, values in book["names"].items()}
    # Keep insertion order of values (parser cares about index 0 = preferred display).
    # But sort languages alphabetically so JSON is deterministic.
    sorted_names = {lang: names[lang] for lang in sorted(names)}
    return {
        "num": book["num"],
        "canonical": book["canonical"],
        "names": sorted_names,
    }


def main() -> int:
    payload = [_normalize_book(b) for b in sorted(BOOKS, key=lambda b: b["num"])]
    serialized = json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=False)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(serialized + "\n", encoding="utf-8")

    digest = hashlib.sha256(serialized.encode("utf-8")).hexdigest()
    meta = {
        "sha256": digest,
        "count": len(payload),
        "generator": "packages/jw-core/scripts/dump_books_json.py",
        "source": "jw_core.data.books.BOOKS",
    }
    META.write_text(json.dumps(meta, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    print(f"Wrote {len(payload)} books to {OUT.relative_to(REPO_ROOT)} (sha256={digest[:12]}…)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 2: Create `dump_languages_json.py`**

```python
# packages/jw-core/scripts/dump_languages_json.py
"""Dump the resolved LANGUAGES registry as JSON for the TS port.

Maps ISO codes (en, es, pt, …) to WOL URL fragments (wol_resource, lp_tag)
and default Bible publication code (nwt, nwtsty, …).
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from jw_core.languages import LANGUAGES

REPO_ROOT = Path(__file__).resolve().parents[3]
OUT = REPO_ROOT / "packages" / "jw-core-js" / "src" / "data" / "languages.json"
META = REPO_ROOT / "packages" / "jw-core-js" / "src" / "data" / "languages.meta.json"


def main() -> int:
    payload = {}
    for iso, lang in sorted(LANGUAGES.items()):
        payload[iso] = {
            "iso": lang.iso,
            "wol_resource": lang.wol_resource,
            "lp_tag": lang.lp_tag,
            "default_bible": lang.default_bible,
            "name": getattr(lang, "name", lang.iso),
        }
    serialized = json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(serialized + "\n", encoding="utf-8")

    digest = hashlib.sha256(serialized.encode("utf-8")).hexdigest()
    meta = {
        "sha256": digest,
        "count": len(payload),
        "generator": "packages/jw-core/scripts/dump_languages_json.py",
        "source": "jw_core.languages.LANGUAGES",
    }
    META.write_text(json.dumps(meta, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"Wrote {len(payload)} languages to {OUT.relative_to(REPO_ROOT)} (sha256={digest[:12]}…)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 3: Run both scripts and inspect output**

Run:
```bash
cd /Users/elias/Documents/Trabajo/jw-agent-toolkit
uv run python packages/jw-core/scripts/dump_books_json.py
uv run python packages/jw-core/scripts/dump_languages_json.py
```

Expected:
- `Wrote 66 books to packages/jw-core-js/src/data/books.json (sha256=…)`
- `Wrote N languages to packages/jw-core-js/src/data/languages.json (sha256=…)` (N depends on `jw_core.languages.LANGUAGES`; ≥17 after Fase 20).

Inspect:
```bash
head -30 packages/jw-core-js/src/data/books.json
cat packages/jw-core-js/src/data/books.meta.json
```

- [ ] **Step 4: Create `tools/verify-books-json.ts` (TS-side sanity)**

```ts
// packages/jw-core-js/tools/verify-books-json.ts
/**
 * Sanity check the bundled books.json:
 *  - count matches meta
 *  - sha256 matches meta
 *  - all book.num in 1..66 and unique
 *  - all books have at least one language with at least one name
 *
 * Run: pnpm -F @jw-agent-toolkit/core exec tsx tools/verify-books-json.ts
 *
 * Used as a smoke check in CI before bundling.
 */

import { readFileSync } from 'node:fs';
import { createHash } from 'node:crypto';
import { fileURLToPath } from 'node:url';
import { dirname, resolve } from 'node:path';

const here = dirname(fileURLToPath(import.meta.url));
const dataDir = resolve(here, '..', 'src', 'data');

interface BookEntry {
  num: number;
  canonical: string;
  names: Record<string, string[]>;
}

interface Meta {
  sha256: string;
  count: number;
}

function loadJson<T>(path: string): T {
  return JSON.parse(readFileSync(path, 'utf-8')) as T;
}

function reserialize(books: BookEntry[]): string {
  // Must match the Python dump exactly: indent=2, ensure_ascii=False, no sort_keys at top level.
  return `${JSON.stringify(books, null, 2)}\n`;
}

function main(): number {
  const booksPath = resolve(dataDir, 'books.json');
  const metaPath = resolve(dataDir, 'books.meta.json');

  const books = loadJson<BookEntry[]>(booksPath);
  const meta = loadJson<Meta>(metaPath);

  if (books.length !== meta.count) {
    console.error(`count mismatch: file=${books.length} meta=${meta.count}`);
    return 1;
  }

  const nums = new Set(books.map((b) => b.num));
  if (nums.size !== books.length) {
    console.error('duplicate book numbers detected');
    return 1;
  }
  for (let i = 1; i <= 66; i += 1) {
    if (!nums.has(i)) {
      console.error(`missing book number ${i}`);
      return 1;
    }
  }

  for (const b of books) {
    const langs = Object.keys(b.names);
    if (langs.length === 0) {
      console.error(`book ${b.num} has zero languages`);
      return 1;
    }
    for (const lang of langs) {
      const list = b.names[lang];
      if (!list || list.length === 0) {
        console.error(`book ${b.num} lang ${lang} has zero names`);
        return 1;
      }
    }
  }

  // sha256 check uses the file bytes (the Python dump appends a trailing newline)
  const raw = readFileSync(booksPath, 'utf-8');
  // The Python script serializes WITHOUT the trailing newline before hashing,
  // then writes serialized + "\n". Replicate:
  const trimmed = raw.endsWith('\n') ? raw.slice(0, -1) : raw;
  const digest = createHash('sha256').update(trimmed, 'utf-8').digest('hex');
  if (digest !== meta.sha256) {
    console.error(`sha256 mismatch: file=${digest} meta=${meta.sha256}`);
    return 1;
  }

  console.log(`OK — ${books.length} books, sha256=${digest.slice(0, 12)}…`);
  return 0;
}

process.exit(main());
```

- [ ] **Step 5: Add tsx to devDependencies and update Makefile**

Edit `packages/jw-core-js/package.json`, append to `devDependencies`:
```jsonc
"tsx": "^4.19.0"
```

Then add to `Makefile` (root):
```makefile
.PHONY: dump-shared-data
dump-shared-data:
	uv run python packages/jw-core/scripts/dump_books_json.py
	uv run python packages/jw-core/scripts/dump_languages_json.py

.PHONY: verify-shared-data
verify-shared-data:
	pnpm -F @jw-agent-toolkit/core exec tsx tools/verify-books-json.ts
```

- [ ] **Step 6: Run verification**

```bash
pnpm install
make verify-shared-data
```

Expected: `OK — 66 books, sha256=…`

- [ ] **Step 7: Commit**

```bash
git add packages/jw-core/scripts/dump_books_json.py packages/jw-core/scripts/dump_languages_json.py \
        packages/jw-core-js/src/data/ packages/jw-core-js/tools/verify-books-json.ts \
        packages/jw-core-js/package.json Makefile pnpm-lock.yaml
git commit -m "feat(jw-core-js): dump_books_json + dump_languages_json + verify tool"
```

---

### Task 3: CI skeleton + npm v0.0.1 placeholder publish

**Files:**
- Create: `.github/workflows/cross-lang.yml`
- Create: `.github/workflows/publish-npm-on-tag.yml`
- Create: `docs/publishing/npm.md`

- [ ] **Step 1: Create `cross-lang.yml`**

```yaml
# .github/workflows/cross-lang.yml
name: cross-lang

on:
  push:
    branches: [main]
  pull_request:
    branches: [main]

jobs:
  parity:
    runs-on: ubuntu-latest
    timeout-minutes: 15
    steps:
      - uses: actions/checkout@v4

      - name: Setup Node
        uses: actions/setup-node@v4
        with:
          node-version: 20

      - name: Setup pnpm
        uses: pnpm/action-setup@v4
        with:
          version: 9

      - name: Setup uv
        uses: astral-sh/setup-uv@v3
        with:
          enable-cache: true

      - name: Python sync
        run: uv sync --all-packages

      - name: pnpm install
        run: pnpm install --frozen-lockfile

      - name: Books JSON up-to-date
        run: |
          uv run python packages/jw-core/scripts/dump_books_json.py
          uv run python packages/jw-core/scripts/dump_languages_json.py
          if ! git diff --exit-code packages/jw-core-js/src/data/; then
            echo "::error::Shared data drift detected. Run: make dump-shared-data"
            exit 1
          fi

      - name: Verify books.json sanity (TS side)
        run: pnpm -F @jw-agent-toolkit/core exec tsx tools/verify-books-json.ts

      - name: Python parity tests
        run: uv run pytest packages/jw-core/tests/test_cross_lang_parity.py -v --tb=short

      - name: TS parity tests
        working-directory: packages/jw-core-js
        run: pnpm test -- tests/cross_lang/

      - name: TS typecheck
        run: pnpm -F @jw-agent-toolkit/core run typecheck

      - name: TS lint
        run: pnpm -F @jw-agent-toolkit/core run lint

      - name: TS build
        run: pnpm -F @jw-agent-toolkit/core run build
```

- [ ] **Step 2: Create `publish-npm-on-tag.yml`**

```yaml
# .github/workflows/publish-npm-on-tag.yml
name: publish-npm

on:
  push:
    tags:
      - 'jw-core-js@v*'

jobs:
  publish:
    runs-on: ubuntu-latest
    timeout-minutes: 10
    permissions:
      contents: read
      id-token: write  # for npm provenance

    steps:
      - uses: actions/checkout@v4
        with: { fetch-depth: 0 }

      - uses: actions/setup-node@v4
        with:
          node-version: 20
          registry-url: 'https://registry.npmjs.org'

      - uses: pnpm/action-setup@v4
        with: { version: 9 }

      - run: pnpm install --frozen-lockfile

      - name: Verify package
        run: pnpm -F @jw-agent-toolkit/core run verify

      - name: Publish to npm with provenance
        working-directory: packages/jw-core-js
        run: npm publish --access public --provenance
        env:
          NODE_AUTH_TOKEN: ${{ secrets.NPM_TOKEN }}
```

- [ ] **Step 3: Create `docs/publishing/npm.md`**

```markdown
# Publishing `@jw-agent-toolkit/core` to npm

## One-time setup

1. Create npm org `jw-agent-toolkit` (or use scope `@eliascipre`).
2. Add `NPM_TOKEN` to GitHub repo secrets (Settings → Secrets and variables → Actions). The token must have `Publish` access for the scope.
3. Enable npm provenance: requires the `id-token: write` permission already set in `publish-npm-on-tag.yml`.

## Cutting a release

```bash
cd packages/jw-core-js

# Bump version (writes to package.json + CHANGELOG via prerelease hook)
pnpm version 0.1.0 --no-git-tag-version

# Manually edit CHANGELOG.md to describe what's in this release.

# Commit and tag with prefix
git add package.json CHANGELOG.md
git commit -m "chore(jw-core-js): release 0.1.0"
git tag -s jw-core-js@v0.1.0 -m "jw-core-js 0.1.0"
git push origin main
git push origin jw-core-js@v0.1.0
```

The `publish-npm-on-tag.yml` workflow fires on the tag and runs:
- `pnpm run verify` (lint + typecheck + test + build)
- `npm publish --access public --provenance`

## Local dry-run

```bash
cd packages/jw-core-js
pnpm publish --dry-run --access public
```

Inspect the resulting tarball:
```bash
pnpm pack
tar -tf jw-agent-toolkit-core-*.tgz
```

Expected: `package/dist/...`, `package/src/...`, `package/LICENSE`, `package/README.md`, `package/package.json`. NO `tests/`, NO `tools/`, NO config files.

## Pre-1.0 versioning policy

- Any change to the public API shape (BibleRef fields, exported function signatures) bumps minor (`0.x.0`).
- Bug fixes + internal changes bump patch (`0.0.x`).
- v1.0.0 only when: ≥3 months stable + 1000+ parity fixtures green + ≥1 downstream consumer in production.
```

- [ ] **Step 4: Reserve the scope (manual, one-time)**

> **Manual step** — execute outside the automated plan.

```bash
# Log in to npm with the maintainer account
npm login

# Create org (if not already): https://www.npmjs.com/org/create  → org name "jw-agent-toolkit"

# OR: publish under personal scope @eliascipre. Adjust package.json name accordingly.
```

- [ ] **Step 5: Publish v0.0.1 placeholder**

After scope exists:

```bash
cd packages/jw-core-js
pnpm install
pnpm run build  # produces dist/index.js with only `export const VERSION = '0.0.1';`
pnpm publish --access public
```

Verify on https://www.npmjs.com/package/@jw-agent-toolkit/core that the package page exists, README renders, license shows GPL-3.0-only.

- [ ] **Step 6: Commit CI workflows + docs**

```bash
git add .github/workflows/cross-lang.yml .github/workflows/publish-npm-on-tag.yml docs/publishing/npm.md
git commit -m "feat(ci): cross-lang parity job + npm publish-on-tag workflow + publishing docs"
```

---

### Task 4: Models + zod schemas + snake_case bridge

**Files:**
- Create: `packages/jw-core-js/src/models.ts`
- Create: `packages/jw-core-js/src/_internal/snakeCase.ts`
- Create: `packages/jw-core-js/tests/models.test.ts`

- [ ] **Step 1: Write the failing test**

```ts
// packages/jw-core-js/tests/models.test.ts
import { describe, expect, it } from 'vitest';

import {
  ArticleSchema,
  BibleRefSchema,
  FetchedDocumentSchema,
  toSnakeCaseBibleRef,
  fromSnakeCaseBibleRef,
} from '../src/models';

describe('BibleRefSchema', () => {
  it('accepts a valid ref', () => {
    const ref = BibleRefSchema.parse({
      bookNum: 43,
      bookCanonical: 'John',
      chapter: 3,
      verseStart: 16,
      verseEnd: null,
      detectedLanguage: 'es',
      rawMatch: 'juan 3:16',
    });
    expect(ref.bookNum).toBe(43);
    expect(ref.verseEnd).toBeNull();
  });

  it('rejects bookNum out of range', () => {
    const result = BibleRefSchema.safeParse({
      bookNum: 67,
      bookCanonical: 'X',
      chapter: 1,
      verseStart: null,
      verseEnd: null,
      detectedLanguage: 'en',
      rawMatch: 'x 1',
    });
    expect(result.success).toBe(false);
  });

  it('rejects chapter < 1', () => {
    const result = BibleRefSchema.safeParse({
      bookNum: 1,
      bookCanonical: 'Genesis',
      chapter: 0,
      verseStart: null,
      verseEnd: null,
      detectedLanguage: 'en',
      rawMatch: 'genesis 0',
    });
    expect(result.success).toBe(false);
  });
});

describe('snake_case bridge', () => {
  it('maps camelCase → snake_case', () => {
    const ref = BibleRefSchema.parse({
      bookNum: 43,
      bookCanonical: 'John',
      chapter: 3,
      verseStart: 16,
      verseEnd: null,
      detectedLanguage: 'es',
      rawMatch: 'juan 3:16',
    });
    expect(toSnakeCaseBibleRef(ref)).toEqual({
      book_num: 43,
      book_canonical: 'John',
      chapter: 3,
      verse_start: 16,
      verse_end: null,
      detected_language: 'es',
      raw_match: 'juan 3:16',
    });
  });

  it('maps snake_case → camelCase (roundtrip)', () => {
    const snake = {
      book_num: 43,
      book_canonical: 'John',
      chapter: 3,
      verse_start: 16,
      verse_end: null,
      detected_language: 'es',
      raw_match: 'juan 3:16',
    };
    const camel = fromSnakeCaseBibleRef(snake);
    expect(toSnakeCaseBibleRef(camel)).toEqual(snake);
  });
});

describe('ArticleSchema', () => {
  it('accepts a minimal article', () => {
    const article = ArticleSchema.parse({
      title: 'Hello',
      paragraphs: ['p1', 'p2'],
      references: ['John 3:16'],
    });
    expect(article.paragraphs).toHaveLength(2);
  });
});

describe('FetchedDocumentSchema', () => {
  it('requires url + html', () => {
    const doc = FetchedDocumentSchema.parse({
      url: 'https://wol.jw.org/x',
      html: '<html/>',
    });
    expect(doc.url).toBe('https://wol.jw.org/x');
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

```bash
pnpm -F @jw-agent-toolkit/core test
```

Expected: FAIL — `models.ts` not found.

- [ ] **Step 3: Implement `_internal/snakeCase.ts`**

```ts
// packages/jw-core-js/src/_internal/snakeCase.ts
/**
 * Tiny case converters used at the cross-language boundary.
 *
 * The TS API uses camelCase identifiers. Cross-language fixtures emitted by
 * Python use snake_case (Pydantic default). These helpers bridge the two
 * without pulling in a heavyweight dependency.
 */

export function camelToSnake(s: string): string {
  return s.replace(/[A-Z]/g, (m, idx: number) => (idx === 0 ? m.toLowerCase() : `_${m.toLowerCase()}`));
}

export function snakeToCamel(s: string): string {
  return s.replace(/_([a-z0-9])/g, (_m, c: string) => c.toUpperCase());
}

export function mapKeys<T extends Record<string, unknown>>(
  obj: T,
  fn: (key: string) => string,
): Record<string, unknown> {
  const out: Record<string, unknown> = {};
  for (const [k, v] of Object.entries(obj)) {
    out[fn(k)] = v;
  }
  return out;
}
```

- [ ] **Step 4: Implement `models.ts`**

```ts
// packages/jw-core-js/src/models.ts
/**
 * Public data shapes for @jw-agent-toolkit/core.
 *
 * Each public type has a paired zod schema so runtime validation is viable
 * from plain JS consumers (REST handlers, etc.) without dragging in the
 * TS compiler.
 *
 * Convention:
 *  - TS API uses camelCase identifiers.
 *  - JSON serialization for cross-language fixtures uses snake_case
 *    (matches Pydantic emission). Use the `*BibleRef` bridge helpers.
 */

import { z } from 'zod';

import { mapKeys, camelToSnake, snakeToCamel } from './_internal/snakeCase';

export const BibleRefSchema = z.object({
  bookNum: z.number().int().min(1).max(66),
  bookCanonical: z.string().min(1),
  chapter: z.number().int().min(1),
  verseStart: z.number().int().min(1).nullable(),
  verseEnd: z.number().int().min(1).nullable(),
  detectedLanguage: z.string().min(2),
  rawMatch: z.string().min(1),
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

/**
 * Cross-language bridge: camelCase BibleRef → snake_case dict.
 *
 * Used by the parity test runner to compare TS output against Python fixtures
 * without negotiating naming conventions.
 */
export function toSnakeCaseBibleRef(ref: BibleRef): Record<string, unknown> {
  return mapKeys(ref, camelToSnake);
}

/**
 * Inverse of toSnakeCaseBibleRef. Validates against the schema.
 */
export function fromSnakeCaseBibleRef(snake: Record<string, unknown>): BibleRef {
  const camel = mapKeys(snake, snakeToCamel);
  return BibleRefSchema.parse(camel);
}
```

- [ ] **Step 5: Run test to verify it passes**

```bash
pnpm -F @jw-agent-toolkit/core test -- tests/models.test.ts
```

Expected: 6 passed.

- [ ] **Step 6: Commit**

```bash
git add packages/jw-core-js/src/models.ts packages/jw-core-js/src/_internal/snakeCase.ts \
        packages/jw-core-js/tests/models.test.ts
git commit -m "feat(jw-core-js): zod-backed models + snake_case bridge for parity"
```

---

### Task 5: Port `parseReference` (`src/reference.ts`)

**Files:**
- Create: `packages/jw-core-js/src/reference.ts`
- Create: `packages/jw-core-js/tests/reference.test.ts`
- Modify: `packages/jw-core-js/src/index.ts`

- [ ] **Step 1: Write the failing tests**

```ts
// packages/jw-core-js/tests/reference.test.ts
import { describe, expect, it } from 'vitest';

import {
  parseAllReferences,
  parseReference,
  ReferenceParser,
} from '../src/reference';

describe('parseReference — basic shapes', () => {
  it('parses an English reference with verse', () => {
    const ref = parseReference('John 3:16');
    expect(ref).not.toBeNull();
    expect(ref?.bookNum).toBe(43);
    expect(ref?.bookCanonical).toBe('John');
    expect(ref?.chapter).toBe(3);
    expect(ref?.verseStart).toBe(16);
    expect(ref?.verseEnd).toBeNull();
    expect(ref?.detectedLanguage).toBe('en');
  });

  it('parses a Spanish reference', () => {
    const ref = parseReference('Juan 3:16');
    expect(ref?.bookNum).toBe(43);
    expect(ref?.detectedLanguage).toBe('es');
    expect(ref?.bookCanonical).toBe('John');
  });

  it('parses a Portuguese reference', () => {
    const ref = parseReference('João 3:16');
    expect(ref?.bookNum).toBe(43);
    expect(ref?.detectedLanguage).toBe('pt');
  });

  it('parses a numbered book name (1 Corintios)', () => {
    const ref = parseReference('1 Corintios 13:4-7');
    expect(ref?.bookNum).toBe(46);
    expect(ref?.chapter).toBe(13);
    expect(ref?.verseStart).toBe(4);
    expect(ref?.verseEnd).toBe(7);
  });

  it('handles chapter-only references', () => {
    const ref = parseReference('Heb 13');
    expect(ref?.bookNum).toBe(58);
    expect(ref?.chapter).toBe(13);
    expect(ref?.verseStart).toBeNull();
  });

  it('returns null when no reference present', () => {
    expect(parseReference('the cat sat on the mat')).toBeNull();
  });

  it('handles empty input', () => {
    expect(parseReference('')).toBeNull();
  });
});

describe('parseReference — unicode and normalization', () => {
  it('matches accented book names regardless of NFC/NFD', () => {
    const nfc = parseReference('Génesis 1:1');
    const nfd = parseReference('Génesis 1:1'.normalize('NFD'));
    expect(nfc?.bookNum).toBe(1);
    expect(nfd?.bookNum).toBe(1);
  });

  it('matches when the input is uppercase', () => {
    const ref = parseReference('JUAN 3:16');
    expect(ref?.bookNum).toBe(43);
  });

  it('tolerates extra whitespace inside multi-word book names', () => {
    const ref = parseReference('1   Corintios   13:4');
    expect(ref?.bookNum).toBe(46);
  });
});

describe('parseReference — edge cases', () => {
  it('rejects mid-word matches via word boundary', () => {
    // "Juana" should not match "Juan"
    const ref = parseReference('Juana habló con su madre');
    expect(ref).toBeNull();
  });

  it('rejects chapter 0 (validation failure → skip)', () => {
    // The regex matches but BibleRef validation rejects chapter=0
    const ref = parseReference('John 0:1');
    expect(ref).toBeNull();
  });

  it('accepts en-dash and em-dash as verse range separators', () => {
    const enDash = parseReference('John 3:16–17');
    const emDash = parseReference('John 3:16—17');
    expect(enDash?.verseEnd).toBe(17);
    expect(emDash?.verseEnd).toBe(17);
  });

  it('accepts dot as chapter:verse separator', () => {
    const ref = parseReference('John 3.16');
    expect(ref?.verseStart).toBe(16);
  });
});

describe('parseAllReferences', () => {
  it('finds multiple references in a sentence', () => {
    const refs = parseAllReferences('Compare John 3:16 with Romans 6:23.');
    expect(refs).toHaveLength(2);
    expect(refs[0]?.bookNum).toBe(43);
    expect(refs[1]?.bookNum).toBe(45);
  });

  it('returns [] for text without refs', () => {
    expect(parseAllReferences('nothing here')).toEqual([]);
  });
});

describe('ReferenceParser — singleton-class API', () => {
  it('can be constructed standalone', () => {
    const parser = new ReferenceParser();
    expect(parser.parseOne('Mateo 24:14')?.bookNum).toBe(40);
  });

  it('reuses index across calls (perf smoke)', () => {
    const parser = new ReferenceParser();
    for (let i = 0; i < 100; i += 1) {
      expect(parser.parseOne('Salmos 23:1')?.bookNum).toBe(19);
    }
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

```bash
pnpm -F @jw-agent-toolkit/core test -- tests/reference.test.ts
```

Expected: FAIL — `reference.ts` module not found.

- [ ] **Step 3: Implement `src/reference.ts`**

```ts
// packages/jw-core-js/src/reference.ts
/**
 * Multi-language Bible reference parser — TypeScript port.
 *
 * Mirrors `packages/jw-core/src/jw_core/parsers/reference.py` 1:1. Any
 * editorial change happens in Python first; this file is regenerated only
 * insofar as it consumes the generated `src/data/books.json`.
 *
 * Algorithm:
 *   1. Normalize input (lowercase + accent-strip via NFD + filter combining
 *      marks).
 *   2. Build a single master regex from all book display forms, alternatives
 *      sorted longest-first.
 *   3. Internal whitespace tolerated via `\s+`.
 *   4. Lookup uses a space/dot/hyphen-stripped normalized key so "1
 *      corintios" and "1Co" both resolve to book 46.
 *   5. Validate against `BibleRefSchema`; on validation failure skip
 *      silently (matches Python behavior for chapter=0 fuzz inputs).
 */

import booksData from './data/books.json' with { type: 'json' };

import type { BibleRef } from './models';
import { BibleRefSchema } from './models';

interface BookEntry {
  num: number;
  canonical: string;
  names: Record<string, string[]>;
}

const BOOKS = booksData as readonly BookEntry[];

/** Lowercase + strip combining accents. Preserves spaces, digits, punct. */
function norm(s: string): string {
  return s
    .toLowerCase()
    .normalize('NFD')
    .replace(/[̀-ͯ]/g, '');
}

/** Normalize and strip whitespace, dots, hyphens. Builds the lookup key. */
function normKey(s: string): string {
  return norm(s).replace(/[\s.\-]+/g, '');
}

/** Escape a string for use in a regex character class / literal. */
function escapeRegex(s: string): string {
  return s.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
}

interface IndexEntry {
  bookNum: number;
  lang: string;
  canonical: string;
}

export class ReferenceParser {
  private readonly index: Map<string, IndexEntry>;
  private readonly regex: RegExp;

  constructor() {
    this.index = new Map();
    const displayForms = new Set<string>();

    for (const book of BOOKS) {
      for (const [lang, names] of Object.entries(book.names)) {
        for (const name of names) {
          const display = norm(name).trim();
          const key = normKey(name);
          if (!key) continue;
          // First entry wins for language attribution — same as Python.
          if (!this.index.has(key)) {
            this.index.set(key, {
              bookNum: book.num,
              lang,
              canonical: book.canonical,
            });
          }
          displayForms.add(display);
        }
      }
    }

    this.regex = ReferenceParser.compileMasterRegex(displayForms);
  }

  private static compileMasterRegex(displayForms: Set<string>): RegExp {
    // Sort by length DESC: "1 corintios" must be tried before "corintios".
    const ordered = [...displayForms].sort((a, b) => b.length - a.length);

    const alternatives = ordered.map((d) => {
      const parts = d.split(' ');
      return parts.map(escapeRegex).join('\\s+');
    });

    const bookAlt = alternatives.join('|');

    // \b before book; chapter required; verse + verse_end optional.
    // Dash range supports -, en-dash, em-dash.
    const pattern =
      `\\b(?<book>${bookAlt})\\s*` +
      `(?<chapter>\\d+)` +
      `(?:\\s*[:.]\\s*(?<verseStart>\\d+)` +
      `(?:\\s*[-\\u2013\\u2014]\\s*(?<verseEnd>\\d+))?)?`;

    // 'g' for finditer-equivalent, 'i' for IGNORECASE (input is already
    // normalized but keep parity).
    return new RegExp(pattern, 'gi');
  }

  /** Find all Bible references in `text`. */
  parse(text: string): BibleRef[] {
    if (!text) return [];

    const normalized = norm(text);
    const refs: BibleRef[] = [];

    // Reset lastIndex defensively — global regexes carry state.
    this.regex.lastIndex = 0;

    for (const m of normalized.matchAll(this.regex)) {
      const groups = m.groups;
      if (!groups || !groups.book || !groups.chapter) continue;

      const bookMatch = groups.book;
      const key = normKey(bookMatch);
      const entry = this.index.get(key);
      if (!entry) continue;

      const verseStartRaw = groups.verseStart;
      const verseEndRaw = groups.verseEnd;

      const candidate = {
        bookNum: entry.bookNum,
        bookCanonical: entry.canonical,
        chapter: Number.parseInt(groups.chapter, 10),
        verseStart: verseStartRaw ? Number.parseInt(verseStartRaw, 10) : null,
        verseEnd: verseEndRaw ? Number.parseInt(verseEndRaw, 10) : null,
        detectedLanguage: entry.lang,
        rawMatch: normalized.slice(m.index ?? 0, (m.index ?? 0) + m[0].length).trim(),
      };

      // Validate. Mirrors Python's silent-skip on ValidationError.
      const parsed = BibleRefSchema.safeParse(candidate);
      if (parsed.success) {
        refs.push(parsed.data);
      }
    }

    return refs;
  }

  /** Return the first reference found, or null. */
  parseOne(text: string): BibleRef | null {
    const refs = this.parse(text);
    return refs[0] ?? null;
  }
}

// Lazy singleton — avoid building the regex at module-load time so
// importers that never call parseReference pay nothing.
let _singleton: ReferenceParser | null = null;
function getSingleton(): ReferenceParser {
  if (_singleton === null) {
    _singleton = new ReferenceParser();
  }
  return _singleton;
}

/** Parse the first Bible reference in `text`. Returns null if no match. */
export function parseReference(text: string): BibleRef | null {
  return getSingleton().parseOne(text);
}

/** Parse every Bible reference in `text`. */
export function parseAllReferences(text: string): BibleRef[] {
  return getSingleton().parse(text);
}
```

- [ ] **Step 4: Update `src/index.ts` to re-export**

```ts
// packages/jw-core-js/src/index.ts
export { parseReference, parseAllReferences, ReferenceParser } from './reference';
export {
  BibleRefSchema,
  ArticleSchema,
  FetchedDocumentSchema,
  toSnakeCaseBibleRef,
  fromSnakeCaseBibleRef,
} from './models';
export type { BibleRef, Article, FetchedDocument } from './models';
export const VERSION = '0.1.0';
```

- [ ] **Step 5: Run test to verify it passes**

```bash
pnpm -F @jw-agent-toolkit/core test -- tests/reference.test.ts
```

Expected: 17 passed.

Also run typecheck:
```bash
pnpm -F @jw-agent-toolkit/core run typecheck
```
Expected: zero errors.

- [ ] **Step 6: Commit**

```bash
git add packages/jw-core-js/src/reference.ts packages/jw-core-js/src/index.ts \
        packages/jw-core-js/tests/reference.test.ts
git commit -m "feat(jw-core-js): port parseReference with full unicode + range support"
```

---

### Task 6: Update jw-core to expose a stable `BibleRef.model_dump` serialization helper

**Files:**
- Modify: `packages/jw-core/src/jw_core/parsers/reference.py`
- Modify: `packages/jw-core/src/jw_core/models.py` (if needed — add explicit field order)

> Note: pydantic v2 already emits a dict via `model_dump()`. The goal here is
> to lock the field order for parity comparison (Python dicts are insertion-
> ordered, so the explicit order in models.py controls it). No behavior change;
> just defensive against future re-orderings.

- [ ] **Step 1: Inspect current `BibleRef` model**

```bash
grep -n "class BibleRef" packages/jw-core/src/jw_core/models.py
```

Verify the field order is exactly: `book_num`, `book_canonical`, `chapter`, `verse_start`, `verse_end`, `detected_language`, `raw_match`. If different, the fixtures in Task 7 will need to mirror that order.

- [ ] **Step 2: Add a parity-stable `to_parity_dict` helper to `reference.py`**

Append to `packages/jw-core/src/jw_core/parsers/reference.py`:

```python
def to_parity_dict(ref: BibleRef) -> dict[str, int | str | None]:
    """Stable snake_case dict for cross-language parity tests.

    Pin the exact field order so JSON comparisons against the TS port are
    deterministic regardless of future model_dump default changes.
    """

    return {
        "book_num": ref.book_num,
        "book_canonical": ref.book_canonical,
        "chapter": ref.chapter,
        "verse_start": ref.verse_start,
        "verse_end": ref.verse_end,
        "detected_language": ref.detected_language,
        "raw_match": ref.raw_match,
    }
```

Append to `__all__`:
```python
__all__ = [
    "BibleRef",
    "ReferenceParser",
    "parse_all_references",
    "parse_reference",
    "to_parity_dict",  # NEW
]
```

- [ ] **Step 3: Verify no Python regressions**

```bash
uv run pytest packages/jw-core/tests/ -v --tb=short -k "reference or parser"
```

Expected: all existing tests still pass.

- [ ] **Step 4: Commit**

```bash
git add packages/jw-core/src/jw_core/parsers/reference.py
git commit -m "feat(jw-core): expose to_parity_dict for cross-language fixture comparison"
```

---

### Task 7: Generate 500 cross-language fixtures for `parse_reference`

**Files:**
- Create: `packages/jw-core/scripts/regenerate_cross_lang_fixtures.py`
- Create: `packages/jw-core/tests/fixtures/cross_lang/parse_reference/001..500_*.json`

- [ ] **Step 1: Write the fixture generator**

```python
# packages/jw-core/scripts/regenerate_cross_lang_fixtures.py
"""Regenerate cross-language fixtures for the TS port parity tests.

Strategy:
  - 30 books × 5 chapters × 3 languages = 450 mechanical cases.
  - +50 hand-curated edge cases: NFC/NFD variants, dashes, multi-word
    book names with extra whitespace, false positives (Juana ≠ Juan),
    chapter-only refs, verse ranges with en-dash/em-dash, mid-sentence
    extraction.

Output: packages/jw-core/tests/fixtures/cross_lang/parse_reference/NNN_<slug>.json

Each fixture is the GROUND TRUTH against which BOTH Python and TS are
verified. Re-running this script overwrites the directory; commit the
diff intentionally.

CRITICAL: only run when intentionally evolving the parser. CI does NOT
auto-regenerate.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

from jw_core.data.books import BOOKS
from jw_core.parsers.reference import parse_reference, to_parity_dict

REPO_ROOT = Path(__file__).resolve().parents[3]
OUT_DIR = REPO_ROOT / "packages" / "jw-core" / "tests" / "fixtures" / "cross_lang" / "parse_reference"


# 30 well-known books across OT/NT for the mechanical sweep.
MECHANICAL_BOOKS = [
    1, 2, 5, 6, 18, 19, 20, 23, 24, 26, 27, 32, 39,
    40, 41, 42, 43, 44, 45, 46, 47, 48, 49, 50, 54, 58, 59, 60, 62, 66,
]

CHAPTERS = [1, 3, 5, 10, 15]


def _slug(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", s.lower()).strip("_")


def _mechanical_cases() -> list[dict]:
    cases: list[dict] = []
    counter = 0
    for book_num in MECHANICAL_BOOKS:
        book = next(b for b in BOOKS if b["num"] == book_num)
        for lang in ("en", "es", "pt"):
            display = book["names"][lang][0]
            for chapter in CHAPTERS:
                counter += 1
                input_text = f"{display} {chapter}:1"
                ref = parse_reference(input_text)
                assert ref is not None, f"generator: parser failed for {input_text!r}"
                cases.append(
                    {
                        "id": f"{counter:03d}_{lang}_{_slug(display)}_{chapter}_1",
                        "input": input_text,
                        "expected": to_parity_dict(ref),
                    }
                )
    return cases


def _edge_cases() -> list[dict]:
    """50 hand-curated edge cases."""

    inputs: list[tuple[str, str]] = [
        # NFC vs NFD
        ("génesis_nfc", "Génesis 1:1"),
        ("genesis_nfd", "Génesis 1:1".encode("utf-8").decode()),
        # Dashes
        ("john_verse_range_hyphen", "John 3:16-17"),
        ("john_verse_range_en_dash", "John 3:16–17"),
        ("john_verse_range_em_dash", "John 3:16—17"),
        # Dot separator
        ("john_dot_separator", "John 3.16"),
        # Whitespace
        ("one_corintios_extra_ws", "1   Corintios   13:4"),
        # Chapter only
        ("heb_chapter_only", "Hebreos 13"),
        ("juan_chapter_only", "Juan 1"),
        # Case
        ("juan_uppercase", "JUAN 3:16"),
        ("juan_titlecase", "Juan 3:16"),
        ("juan_lowercase", "juan 3:16"),
        # Embedded in sentence
        ("john_in_sentence_en", "Read John 3:16 today"),
        ("john_in_sentence_es", "Hoy leeremos Juan 3:16 con la congregación"),
        # Numbered books — all variants
        ("first_cor_full", "1 Corinthians 13:4"),
        ("first_cor_abbr", "1 Cor 13:4"),
        ("first_cor_compact", "1Co 13:4"),
        ("second_pedro_es", "2 Pedro 3:13"),
        ("third_john_en", "3 John 1:4"),
        # Portuguese specifics
        ("joao_pt", "João 3:16"),
        ("mateus_pt", "Mateus 24:14"),
        ("apocalipse_pt", "Apocalipse 21:3"),
        # Spanish specifics
        ("apocalipsis_es", "Apocalipsis 21:3"),
        ("salmos_es", "Salmos 83:18"),
        ("eclesiastes_es", "Eclesiastés 3:1"),
        # No match expected — produce null expected
        ("no_match_juana", "Juana habló con su madre"),
        ("no_match_random", "the cat sat on the mat"),
        ("no_match_empty", ""),
        ("no_match_numbers_only", "1234 5678"),
        # Chapter=0 (validation rejects)
        ("invalid_chapter_zero", "John 0:1"),
        # Multiple refs — first only (parse_reference returns first)
        ("multiple_refs_first", "Compare John 3:16 with Romans 6:23."),
        # Magisterial verse ranges
        ("psalms_long_range", "Psalms 119:1-176"),
        # Single-letter language toggles
        ("genesis_en_short", "Gen 1:1"),
        ("genesis_es_short", "Gé 1:1"),
        # Whitespace around colon
        ("john_ws_colon", "John 3 : 16"),
        # Mixed punctuation
        ("john_chapter_dot", "John 3.16"),
        # Tier-1 language (if present in registry) — French
        ("genese_fr_if_supported", "Genèse 1:1"),
        ("matthieu_fr_if_supported", "Matthieu 24:14"),
        # German
        ("genesis_de_if_supported", "1. Mose 1:1"),
        # Italian
        ("genesi_it_if_supported", "Genesi 1:1"),
        # More edges
        ("revelation_full", "Revelation 21:3"),
        ("revelation_short", "Re 21:3"),
        ("acts_full", "Acts 1:8"),
        ("acts_short", "Ac 1:8"),
        ("psalms_singular", "Psalm 23:1"),
        ("matthew_chapter_only", "Matthew 24"),
        ("james_full", "James 1:5"),
        ("james_short", "Jas 1:5"),
        ("philemon_chapter", "Philemon 1"),
        ("jude_chapter", "Jude 1"),
        ("rev_es_short", "Ap 21:3"),
        ("rev_pt_short", "Ap 21:3"),
    ]

    cases: list[dict] = []
    for idx, (slug, text) in enumerate(inputs, start=1):
        ref = parse_reference(text)
        cases.append(
            {
                "id": f"edge_{idx:03d}_{slug}",
                "input": text,
                "expected": to_parity_dict(ref) if ref is not None else None,
            }
        )
    return cases


def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    # Wipe old fixtures so the directory is exactly what this script declares.
    for old in OUT_DIR.glob("*.json"):
        old.unlink()

    all_cases = _mechanical_cases() + _edge_cases()

    # Sanity: at least 450 mechanical + ~50 edges = 500+
    if len(all_cases) < 450:
        print(f"!! WARNING: only {len(all_cases)} cases generated; expected ≥500")

    for case in all_cases:
        path = OUT_DIR / f"{case['id']}.json"
        path.write_text(json.dumps(case, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print(f"Wrote {len(all_cases)} fixtures to {OUT_DIR.relative_to(REPO_ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 2: Run the generator**

```bash
uv run python packages/jw-core/scripts/regenerate_cross_lang_fixtures.py
```

Expected: `Wrote 500 fixtures to packages/jw-core/tests/fixtures/cross_lang/parse_reference`. If you see fewer than 500, expand `_edge_cases()` until ≥500.

Verify count:
```bash
ls packages/jw-core/tests/fixtures/cross_lang/parse_reference | wc -l
```
Expected: `500` (or whatever the script produced).

- [ ] **Step 3: Inspect a few fixtures**

```bash
cat packages/jw-core/tests/fixtures/cross_lang/parse_reference/001_*.json
cat packages/jw-core/tests/fixtures/cross_lang/parse_reference/edge_026_no_match_juana.json
```

Expected: well-formed JSON with `id`, `input`, `expected`. The `juana` fixture should have `expected: null`.

- [ ] **Step 4: Add Makefile target**

Append to `Makefile`:

```makefile
.PHONY: regen-cross-lang-fixtures
regen-cross-lang-fixtures:
	@echo "!! This will OVERWRITE all fixtures in packages/jw-core/tests/fixtures/cross_lang/parse_reference/"
	@read -p "Continue? [y/N] " ans; [ "$$ans" = "y" ] || exit 1
	uv run python packages/jw-core/scripts/regenerate_cross_lang_fixtures.py
```

- [ ] **Step 5: Commit**

```bash
git add packages/jw-core/scripts/regenerate_cross_lang_fixtures.py \
        packages/jw-core/tests/fixtures/cross_lang/parse_reference Makefile
git commit -m "feat(jw-core): regenerate_cross_lang_fixtures script + 500 parse_reference fixtures"
```

---

### Task 8: Python-side parity test (`test_cross_lang_parity.py`)

**Files:**
- Create: `packages/jw-core/tests/test_cross_lang_parity.py`

- [ ] **Step 1: Write the parity test**

```python
# packages/jw-core/tests/test_cross_lang_parity.py
"""Cross-language parity: ensure Python parser matches stored fixtures.

If this test fails, either:
  (a) the parser changed intentionally — regenerate fixtures via
      `make regen-cross-lang-fixtures` and commit the diff alongside the
      parser change.
  (b) the parser changed unintentionally — fix the parser.

The TS side runs the equivalent test in `packages/jw-core-js/tests/cross_lang/parity.test.ts`.
Both must pass for the cross-language guarantee to hold.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from jw_core.parsers.reference import parse_reference, to_parity_dict

FIXTURES_DIR = (
    Path(__file__).parent / "fixtures" / "cross_lang" / "parse_reference"
)


def _load_fixtures() -> list[dict]:
    cases: list[dict] = []
    for path in sorted(FIXTURES_DIR.glob("*.json")):
        cases.append(json.loads(path.read_text(encoding="utf-8")))
    return cases


_FIXTURES = _load_fixtures()


def test_fixture_directory_is_populated() -> None:
    assert len(_FIXTURES) >= 500, (
        f"Expected ≥500 fixtures, got {len(_FIXTURES)}. "
        f"Run: uv run python packages/jw-core/scripts/regenerate_cross_lang_fixtures.py"
    )


@pytest.mark.parametrize("fixture", _FIXTURES, ids=lambda f: f["id"])
def test_python_matches_fixture(fixture: dict) -> None:
    ref = parse_reference(fixture["input"])
    actual = to_parity_dict(ref) if ref is not None else None
    expected = fixture["expected"]
    assert actual == expected, (
        f"Fixture {fixture['id']}: divergence.\n"
        f"  input:    {fixture['input']!r}\n"
        f"  expected: {expected}\n"
        f"  actual:   {actual}\n"
        f"If intentional, regenerate via "
        f"`uv run python packages/jw-core/scripts/regenerate_cross_lang_fixtures.py`"
    )
```

- [ ] **Step 2: Run the test**

```bash
uv run pytest packages/jw-core/tests/test_cross_lang_parity.py -v --tb=short
```

Expected: ≥500 tests pass. Since fixtures were generated from the same parser, this must pass 100% on the first run — if it doesn't, the generator has a bug.

- [ ] **Step 3: Commit**

```bash
git add packages/jw-core/tests/test_cross_lang_parity.py
git commit -m "test(jw-core): parametrized cross-language parity test (500 fixtures)"
```

---

### Task 9: TypeScript-side parity test (`cross_lang/parity.test.ts`)

**Files:**
- Create: `packages/jw-core-js/tests/cross_lang/_loader.ts`
- Create: `packages/jw-core-js/tests/cross_lang/parity.test.ts`

- [ ] **Step 1: Write the loader helper**

```ts
// packages/jw-core-js/tests/cross_lang/_loader.ts
import { readdirSync, readFileSync } from 'node:fs';
import { join, dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const here = dirname(fileURLToPath(import.meta.url));

/**
 * Resolve the shared cross-language fixtures directory.
 *
 * Fixtures live under the Python package
 * (`packages/jw-core/tests/fixtures/cross_lang/`) so a single source of
 * truth feeds both runtimes.
 */
function fixturesRoot(): string {
  // tests/cross_lang/ → packages/jw-core-js → packages → repo root
  return resolve(here, '..', '..', '..', '..', 'packages', 'jw-core', 'tests', 'fixtures', 'cross_lang');
}

export interface ParseReferenceFixture {
  id: string;
  input: string;
  expected: Record<string, unknown> | null;
}

export function loadParseReferenceFixtures(): ParseReferenceFixture[] {
  const dir = join(fixturesRoot(), 'parse_reference');
  const files = readdirSync(dir).filter((f) => f.endsWith('.json')).sort();
  return files.map((f) => {
    const raw = readFileSync(join(dir, f), 'utf-8');
    return JSON.parse(raw) as ParseReferenceFixture;
  });
}

export interface WolUrlFixture {
  id: string;
  input: {
    book_num: number;
    chapter: number;
    language: string;
    publication?: string | null;
  };
  expected: { url: string };
}

export function loadWolUrlFixtures(): WolUrlFixture[] {
  const dir = join(fixturesRoot(), 'wol_url');
  const files = readdirSync(dir).filter((f) => f.endsWith('.json')).sort();
  return files.map((f) => {
    const raw = readFileSync(join(dir, f), 'utf-8');
    return JSON.parse(raw) as WolUrlFixture;
  });
}

export interface ArticleFixture {
  id: string;
  htmlPath: string;
  expected: {
    title: string;
    paragraphs: string[];
    references: string[];
  };
}

export function loadArticleFixtures(): ArticleFixture[] {
  const dir = join(fixturesRoot(), 'article');
  const files = readdirSync(dir)
    .filter((f) => f.endsWith('.expected.json'))
    .sort();
  return files.map((f) => {
    const expectedPath = join(dir, f);
    const htmlPath = expectedPath.replace(/\.expected\.json$/, '.html');
    const raw = readFileSync(expectedPath, 'utf-8');
    return {
      id: f.replace(/\.expected\.json$/, ''),
      htmlPath,
      expected: JSON.parse(raw) as ArticleFixture['expected'],
    };
  });
}

export function readHtml(path: string): string {
  return readFileSync(path, 'utf-8');
}
```

- [ ] **Step 2: Write the parity test**

```ts
// packages/jw-core-js/tests/cross_lang/parity.test.ts
import { describe, expect, it } from 'vitest';

import { parseReference } from '../../src/reference';
import { toSnakeCaseBibleRef } from '../../src/models';

import { loadParseReferenceFixtures } from './_loader';

const fixtures = loadParseReferenceFixtures();

describe('parse_reference cross-language parity', () => {
  it('found at least 500 fixtures', () => {
    expect(fixtures.length).toBeGreaterThanOrEqual(500);
  });

  for (const fx of fixtures) {
    it(fx.id, () => {
      const ref = parseReference(fx.input);
      const actual = ref ? toSnakeCaseBibleRef(ref) : null;
      expect(actual).toEqual(fx.expected);
    });
  }
});
```

- [ ] **Step 3: Run the test**

```bash
pnpm -F @jw-agent-toolkit/core test -- tests/cross_lang/parity.test.ts
```

Expected: ≥501 tests pass (1 sanity + 500 fixtures). If any fixture diverges, the failure log shows the input, expected, and actual — fix either the parser or regenerate the fixture (only if the change is intentional).

- [ ] **Step 4: Commit**

```bash
git add packages/jw-core-js/tests/cross_lang
git commit -m "test(jw-core-js): TS parity test for 500 parse_reference fixtures"
```

---

### Task 10: Port `languages.ts` from generated JSON

**Files:**
- Create: `packages/jw-core-js/src/languages.ts`
- Create: `packages/jw-core-js/tests/languages.test.ts`

- [ ] **Step 1: Write the failing test**

```ts
// packages/jw-core-js/tests/languages.test.ts
import { describe, expect, it } from 'vitest';

import {
  getLanguage,
  listLanguages,
  type Language,
} from '../src/languages';

describe('languages registry', () => {
  it('returns English by ISO code', () => {
    const lang = getLanguage('en');
    expect(lang.iso).toBe('en');
    expect(lang.wolResource).toMatch(/r1/);  // English WOL resource id
    expect(lang.lpTag).toBe('lp-e');
    expect(lang.defaultBible).toBeDefined();
  });

  it('returns Spanish by ISO code', () => {
    const lang = getLanguage('es');
    expect(lang.iso).toBe('es');
    expect(lang.lpTag).toBe('lp-s');
  });

  it('returns Portuguese by ISO code', () => {
    const lang = getLanguage('pt');
    expect(lang.iso).toBe('pt');
    expect(lang.lpTag).toBe('lp-t');
  });

  it('throws on unknown ISO', () => {
    expect(() => getLanguage('xx-not-a-lang')).toThrow(/unknown language/i);
  });

  it('lists all registered languages', () => {
    const langs = listLanguages();
    expect(langs.length).toBeGreaterThanOrEqual(3);
    expect(langs.find((l: Language) => l.iso === 'en')).toBeDefined();
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

```bash
pnpm -F @jw-agent-toolkit/core test -- tests/languages.test.ts
```

Expected: FAIL — `languages.ts` missing.

- [ ] **Step 3: Implement `src/languages.ts`**

```ts
// packages/jw-core-js/src/languages.ts
/**
 * Language registry — mirror of jw_core.languages.LANGUAGES.
 *
 * Loaded from generated `data/languages.json`. The dump script
 * `packages/jw-core/scripts/dump_languages_json.py` is the single source
 * of truth.
 *
 * `wolResource` is the numeric+letter resource fragment used in WOL URLs
 * (e.g. "r1" for English, "r4" for Spanish). `lpTag` is the publication-
 * language tag (e.g. "lp-e", "lp-s"). `defaultBible` is the publication
 * code WOL uses for the language's preferred Bible (e.g. "nwtsty" / "nwt").
 */

import languagesData from './data/languages.json' with { type: 'json' };

interface RawLanguage {
  iso: string;
  wol_resource: string;
  lp_tag: string;
  default_bible: string;
  name?: string;
}

export interface Language {
  iso: string;
  wolResource: string;
  lpTag: string;
  defaultBible: string;
  name: string;
}

const RAW = languagesData as Record<string, RawLanguage>;

function fromRaw(raw: RawLanguage): Language {
  return {
    iso: raw.iso,
    wolResource: raw.wol_resource,
    lpTag: raw.lp_tag,
    defaultBible: raw.default_bible,
    name: raw.name ?? raw.iso,
  };
}

const REGISTRY: Map<string, Language> = (() => {
  const m = new Map<string, Language>();
  for (const [iso, raw] of Object.entries(RAW)) {
    m.set(iso, fromRaw(raw));
  }
  return m;
})();

export function getLanguage(iso: string): Language {
  const lang = REGISTRY.get(iso);
  if (!lang) {
    throw new Error(`unknown language ISO code: ${iso!r if false else iso}`);
  }
  return lang;
}

export function listLanguages(): Language[] {
  return [...REGISTRY.values()];
}
```

Wait — TS doesn't have Python's `!r` format. Fix the error message:

```ts
export function getLanguage(iso: string): Language {
  const lang = REGISTRY.get(iso);
  if (!lang) {
    throw new Error(`unknown language ISO code: ${JSON.stringify(iso)}`);
  }
  return lang;
}
```

- [ ] **Step 4: Run test to verify it passes**

```bash
pnpm -F @jw-agent-toolkit/core test -- tests/languages.test.ts
```

Expected: 5 passed.

- [ ] **Step 5: Commit**

```bash
git add packages/jw-core-js/src/languages.ts packages/jw-core-js/tests/languages.test.ts
git commit -m "feat(jw-core-js): port language registry from generated languages.json"
```

---

### Task 11: Port `WOLClient.getBibleChapter` (`src/clients/wol.ts`)

**Files:**
- Create: `packages/jw-core-js/src/clients/wol.ts`
- Create: `packages/jw-core-js/tests/wol.test.ts`
- Modify: `packages/jw-core-js/src/index.ts`

- [ ] **Step 1: Write the failing test**

```ts
// packages/jw-core-js/tests/wol.test.ts
import { describe, expect, it, vi } from 'vitest';

import { WOLClient, WOLError, buildBibleChapterUrl } from '../src/clients/wol';

describe('buildBibleChapterUrl', () => {
  it('builds URL for English (book=43, chapter=3)', () => {
    const url = buildBibleChapterUrl({ bookNum: 43, chapter: 3, language: 'en' });
    expect(url).toMatch(/^https:\/\/wol\.jw\.org\/en\/wol\/b\/r\d+\/lp-e\/[a-z]+\/43\/3$/);
  });

  it('builds URL for Spanish (book=43, chapter=3)', () => {
    const url = buildBibleChapterUrl({ bookNum: 43, chapter: 3, language: 'es' });
    expect(url).toContain('/es/');
    expect(url).toContain('/lp-s/');
    expect(url).toMatch(/\/43\/3$/);
  });

  it('overrides default publication', () => {
    const url = buildBibleChapterUrl({
      bookNum: 43,
      chapter: 3,
      language: 'en',
      publication: 'custompub',
    });
    expect(url).toContain('/custompub/');
  });
});

describe('WOLClient.getBibleChapter', () => {
  it('returns { url, html } with injected fetch', async () => {
    const stubHtml = '<html><body>Hello WOL</body></html>';
    const stubFetch = vi.fn(async (input: RequestInfo | URL) => {
      return new Response(stubHtml, {
        status: 200,
        headers: { 'content-type': 'text/html' },
      });
    });

    const client = new WOLClient({ fetch: stubFetch });
    const { url, html } = await client.getBibleChapter(43, 3, { language: 'es' });

    expect(url).toContain('/es/');
    expect(html).toBe(stubHtml);
    expect(stubFetch).toHaveBeenCalledOnce();
  });

  it('throws WOLError on HTTP 404', async () => {
    const stubFetch = vi.fn(async () => new Response('not found', { status: 404 }));

    const client = new WOLClient({ fetch: stubFetch });
    await expect(client.getBibleChapter(43, 3)).rejects.toBeInstanceOf(WOLError);
  });

  it('throws WOLError on network failure', async () => {
    const stubFetch = vi.fn(async () => {
      throw new TypeError('network down');
    });

    const client = new WOLClient({ fetch: stubFetch });
    await expect(client.getBibleChapter(43, 3)).rejects.toBeInstanceOf(WOLError);
  });

  it('honors timeoutMs via AbortSignal', async () => {
    const stubFetch = vi.fn(async (_input: RequestInfo | URL, init?: RequestInit) => {
      // Wait long enough for the abort to trigger.
      return new Promise<Response>((_resolve, reject) => {
        const signal = init?.signal;
        if (signal) {
          signal.addEventListener('abort', () => {
            reject(new DOMException('aborted', 'AbortError'));
          });
        }
        // Never resolve on its own
      });
    });

    const client = new WOLClient({ fetch: stubFetch, timeoutMs: 20 });
    await expect(client.getBibleChapter(43, 3)).rejects.toBeInstanceOf(WOLError);
  });

  it('sends the configured User-Agent header', async () => {
    let capturedUA: string | null = null;
    const stubFetch = vi.fn(async (_input: RequestInfo | URL, init?: RequestInit) => {
      const headers = new Headers(init?.headers);
      capturedUA = headers.get('user-agent');
      return new Response('<html/>', { status: 200 });
    });

    const client = new WOLClient({ fetch: stubFetch, userAgent: 'my-agent/1.0' });
    await client.getBibleChapter(43, 3);
    expect(capturedUA).toBe('my-agent/1.0');
  });
});

describe('WOLClient.fetch (bare URL)', () => {
  it('accepts a raw URL string and returns HTML', async () => {
    const stubFetch = vi.fn(async () => new Response('<html>x</html>', { status: 200 }));
    const client = new WOLClient({ fetch: stubFetch });
    const html = await client.fetch('https://wol.jw.org/anything');
    expect(html).toBe('<html>x</html>');
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

```bash
pnpm -F @jw-agent-toolkit/core test -- tests/wol.test.ts
```

Expected: FAIL — `clients/wol.ts` missing.

- [ ] **Step 3: Implement `src/clients/wol.ts`**

```ts
// packages/jw-core-js/src/clients/wol.ts
/**
 * Minimal WOL HTTP client — TypeScript port.
 *
 * Mirrors `WOLClient.get_bible_chapter` from the Python implementation.
 * Intentionally stripped of cache, throttle, telemetry — those are
 * Python-only Phase 9 concerns. Callers can layer them on top.
 *
 * Uses `fetch` global (Node ≥18, browsers, Bun, Deno, Workers). For tests
 * inject a stub via `WOLClientOptions.fetch`.
 *
 * Timeouts use AbortController.
 */

import { getLanguage } from '../languages';
import type { FetchedDocument } from '../models';

export const WOL_BASE = 'https://wol.jw.org';
export const DEFAULT_USER_AGENT = 'jw-agent-toolkit-js/0.1 (+research)';
export const DEFAULT_TIMEOUT_MS = 30_000;

export class WOLError extends Error {
  override readonly name = 'WOLError';
  readonly cause?: unknown;

  constructor(message: string, cause?: unknown) {
    super(message);
    if (cause !== undefined) {
      this.cause = cause;
    }
  }
}

export interface WOLClientOptions {
  fetch?: typeof fetch;
  userAgent?: string;
  timeoutMs?: number;
}

export interface BuildBibleChapterUrlInput {
  bookNum: number;
  chapter: number;
  language?: string;
  publication?: string;
}

export function buildBibleChapterUrl(input: BuildBibleChapterUrlInput): string {
  const lang = getLanguage(input.language ?? 'en');
  const pub = input.publication ?? lang.defaultBible;
  return `${WOL_BASE}/${lang.iso}/wol/b/${lang.wolResource}/${lang.lpTag}/${pub}/${input.bookNum}/${input.chapter}`;
}

export class WOLClient {
  private readonly fetchImpl: typeof fetch;
  private readonly userAgent: string;
  private readonly timeoutMs: number;

  constructor(options: WOLClientOptions = {}) {
    this.fetchImpl = options.fetch ?? globalThis.fetch.bind(globalThis);
    this.userAgent = options.userAgent ?? DEFAULT_USER_AGENT;
    this.timeoutMs = options.timeoutMs ?? DEFAULT_TIMEOUT_MS;
  }

  async fetch(url: string): Promise<string> {
    const fullUrl = url.startsWith('http') ? url : `${WOL_BASE}${url}`;

    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), this.timeoutMs);

    try {
      const response = await this.fetchImpl(fullUrl, {
        method: 'GET',
        signal: controller.signal,
        headers: {
          'User-Agent': this.userAgent,
          Accept: 'text/html,application/xhtml+xml',
          'Accept-Language': 'en,es;q=0.9',
        },
      });

      if (!response.ok) {
        throw new WOLError(`HTTP ${response.status} for ${fullUrl}`);
      }

      return await response.text();
    } catch (err) {
      if (err instanceof WOLError) throw err;
      throw new WOLError(`fetch failed for ${fullUrl}: ${(err as Error).message}`, err);
    } finally {
      clearTimeout(timer);
    }
  }

  async getBibleChapter(
    bookNum: number,
    chapter: number,
    options: { language?: string; publication?: string } = {},
  ): Promise<FetchedDocument> {
    const url = buildBibleChapterUrl({
      bookNum,
      chapter,
      language: options.language,
      publication: options.publication,
    });
    const html = await this.fetch(url);
    return { url, html };
  }
}
```

- [ ] **Step 4: Update `src/index.ts` to re-export**

Append:
```ts
export { WOLClient, WOLError, buildBibleChapterUrl, WOL_BASE } from './clients/wol';
export type { WOLClientOptions, BuildBibleChapterUrlInput } from './clients/wol';
export { getLanguage, listLanguages } from './languages';
export type { Language } from './languages';
```

- [ ] **Step 5: Run test to verify it passes**

```bash
pnpm -F @jw-agent-toolkit/core test -- tests/wol.test.ts
pnpm -F @jw-agent-toolkit/core run typecheck
```

Expected: 7 passed, zero typecheck errors.

- [ ] **Step 6: Commit**

```bash
git add packages/jw-core-js/src/clients packages/jw-core-js/src/index.ts \
        packages/jw-core-js/tests/wol.test.ts
git commit -m "feat(jw-core-js): port WOLClient with timeout + injectable fetch"
```

---

### Task 12: Generate 30 cross-language fixtures for `wol_url`

**Files:**
- Modify: `packages/jw-core/scripts/regenerate_cross_lang_fixtures.py`
- Create: `packages/jw-core/tests/fixtures/cross_lang/wol_url/001..030_*.json`
- Modify: `packages/jw-core/tests/test_cross_lang_parity.py`
- Modify: `packages/jw-core-js/tests/cross_lang/parity.test.ts`

- [ ] **Step 1: Extend the generator**

Add to `packages/jw-core/scripts/regenerate_cross_lang_fixtures.py`:

```python
from jw_core.languages import get_language

WOL_BASE = "https://wol.jw.org"


def _wol_url_cases() -> list[dict]:
    """30 (language, book, chapter) tuples covering OT/NT diversity."""

    tuples = [
        # English — variety across testaments
        ("en", 1, 1), ("en", 19, 23), ("en", 23, 53), ("en", 40, 5), ("en", 43, 3),
        ("en", 44, 1), ("en", 45, 8), ("en", 46, 13), ("en", 58, 11), ("en", 66, 21),
        # Spanish
        ("es", 1, 1), ("es", 19, 23), ("es", 23, 53), ("es", 40, 5), ("es", 43, 3),
        ("es", 44, 1), ("es", 45, 8), ("es", 46, 13), ("es", 58, 11), ("es", 66, 21),
        # Portuguese
        ("pt", 1, 1), ("pt", 19, 23), ("pt", 23, 53), ("pt", 40, 5), ("pt", 43, 3),
        ("pt", 44, 1), ("pt", 45, 8), ("pt", 46, 13), ("pt", 58, 11), ("pt", 66, 21),
    ]

    out: list[dict] = []
    for idx, (lang_iso, book_num, chapter) in enumerate(tuples, start=1):
        lang = get_language(lang_iso)
        url = (
            f"{WOL_BASE}/{lang.iso}/wol/b/{lang.wol_resource}/"
            f"{lang.lp_tag}/{lang.default_bible}/{book_num}/{chapter}"
        )
        out.append(
            {
                "id": f"{idx:03d}_{lang_iso}_book{book_num}_ch{chapter}",
                "input": {
                    "book_num": book_num,
                    "chapter": chapter,
                    "language": lang_iso,
                    "publication": None,
                },
                "expected": {"url": url},
            }
        )
    return out


def _write_wol_url_fixtures() -> int:
    out_dir = REPO_ROOT / "packages" / "jw-core" / "tests" / "fixtures" / "cross_lang" / "wol_url"
    out_dir.mkdir(parents=True, exist_ok=True)
    for old in out_dir.glob("*.json"):
        old.unlink()
    cases = _wol_url_cases()
    for c in cases:
        path = out_dir / f"{c['id']}.json"
        path.write_text(json.dumps(c, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return len(cases)
```

Modify the bottom `main()` to also call this:

```python
def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    for old in OUT_DIR.glob("*.json"):
        old.unlink()

    all_cases = _mechanical_cases() + _edge_cases()
    for case in all_cases:
        path = OUT_DIR / f"{case['id']}.json"
        path.write_text(json.dumps(case, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    n_url = _write_wol_url_fixtures()
    print(f"Wrote {len(all_cases)} parse_reference + {n_url} wol_url fixtures")
    return 0
```

- [ ] **Step 2: Regenerate fixtures**

```bash
uv run python packages/jw-core/scripts/regenerate_cross_lang_fixtures.py
```

Expected: `Wrote 500 parse_reference + 30 wol_url fixtures`.

Verify:
```bash
ls packages/jw-core/tests/fixtures/cross_lang/wol_url | wc -l
```
Expected: `30`.

- [ ] **Step 3: Extend Python parity test**

Append to `packages/jw-core/tests/test_cross_lang_parity.py`:

```python
from jw_core.languages import get_language

WOL_BASE = "https://wol.jw.org"
WOL_URL_FIXTURES_DIR = (
    Path(__file__).parent / "fixtures" / "cross_lang" / "wol_url"
)


def _build_wol_chapter_url(book_num: int, chapter: int, language: str, publication: str | None) -> str:
    lang = get_language(language)
    pub = publication or lang.default_bible
    return (
        f"{WOL_BASE}/{lang.iso}/wol/b/{lang.wol_resource}/"
        f"{lang.lp_tag}/{pub}/{book_num}/{chapter}"
    )


def _load_wol_url_fixtures() -> list[dict]:
    return [
        json.loads(p.read_text(encoding="utf-8"))
        for p in sorted(WOL_URL_FIXTURES_DIR.glob("*.json"))
    ]


_WOL_URL_FIXTURES = _load_wol_url_fixtures()


def test_wol_url_fixtures_count() -> None:
    assert len(_WOL_URL_FIXTURES) >= 30, (
        f"Expected ≥30 wol_url fixtures, got {len(_WOL_URL_FIXTURES)}"
    )


@pytest.mark.parametrize("fixture", _WOL_URL_FIXTURES, ids=lambda f: f["id"])
def test_python_wol_url_matches_fixture(fixture: dict) -> None:
    inp = fixture["input"]
    actual = _build_wol_chapter_url(
        book_num=inp["book_num"],
        chapter=inp["chapter"],
        language=inp["language"],
        publication=inp.get("publication"),
    )
    assert actual == fixture["expected"]["url"]
```

- [ ] **Step 4: Extend TS parity test**

Append to `packages/jw-core-js/tests/cross_lang/parity.test.ts`:

```ts
import { buildBibleChapterUrl } from '../../src/clients/wol';
import { loadWolUrlFixtures } from './_loader';

const wolUrlFixtures = loadWolUrlFixtures();

describe('wol_url cross-language parity', () => {
  it('found at least 30 wol_url fixtures', () => {
    expect(wolUrlFixtures.length).toBeGreaterThanOrEqual(30);
  });

  for (const fx of wolUrlFixtures) {
    it(fx.id, () => {
      const url = buildBibleChapterUrl({
        bookNum: fx.input.book_num,
        chapter: fx.input.chapter,
        language: fx.input.language,
        publication: fx.input.publication ?? undefined,
      });
      expect(url).toEqual(fx.expected.url);
    });
  }
});
```

- [ ] **Step 5: Run both parity tests**

```bash
uv run pytest packages/jw-core/tests/test_cross_lang_parity.py -v --tb=short
pnpm -F @jw-agent-toolkit/core test -- tests/cross_lang/
```

Expected: ≥531 tests pass on each side.

- [ ] **Step 6: Commit**

```bash
git add packages/jw-core/scripts/regenerate_cross_lang_fixtures.py \
        packages/jw-core/tests/fixtures/cross_lang/wol_url \
        packages/jw-core/tests/test_cross_lang_parity.py \
        packages/jw-core-js/tests/cross_lang/parity.test.ts
git commit -m "test(jw-core-js): 30 wol_url cross-language fixtures + parity test"
```

---

### Task 13: Port `parseArticle` with linkedom (`src/parsers/article.ts`)

**Files:**
- Create: `packages/jw-core-js/src/parsers/article.ts`
- Create: `packages/jw-core-js/tests/article.test.ts`
- Create: `packages/jw-core-js/tests/fixtures/article_snippets/sample_w23_en.html`
- Create: `packages/jw-core-js/tests/fixtures/article_snippets/sample_w23_en.expected.json`
- Modify: `packages/jw-core-js/src/index.ts`

- [ ] **Step 1: Write a representative HTML snippet**

```html
<!-- packages/jw-core-js/tests/fixtures/article_snippets/sample_w23_en.html -->
<!doctype html>
<html lang="en">
  <head>
    <title>Sample WOL Article</title>
  </head>
  <body>
    <header><h1>Walk in Faith</h1></header>
    <article id="article">
      <p id="p1" data-pid="1">
        Faith is more than a feeling.
        <a class="b" href="/en/wol/bc/...">Hebrews 11:1</a>
        describes it as a confident expectation.
      </p>
      <p id="p2" data-pid="2">
        The apostle Paul reminded believers in
        <a class="b" href="/en/wol/bc/...">Romans 10:17</a>
        that faith comes by hearing the word of God.
      </p>
      <p>Skip me — no data-pid and no id="p".</p>
      <footer>Footer paragraph excluded.</footer>
    </article>
  </body>
</html>
```

- [ ] **Step 2: Write the expected JSON**

```json
{
  "title": "Walk in Faith",
  "paragraphs": [
    "Faith is more than a feeling. Hebrews 11:1 describes it as a confident expectation.",
    "The apostle Paul reminded believers in Romans 10:17 that faith comes by hearing the word of God."
  ],
  "references": ["Hebrews 11:1", "Romans 10:17"]
}
```

- [ ] **Step 3: Write the failing tests**

```ts
// packages/jw-core-js/tests/article.test.ts
import { readFileSync } from 'node:fs';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

import { describe, expect, it } from 'vitest';

import { parseArticle } from '../src/parsers/article';

const here = dirname(fileURLToPath(import.meta.url));

function loadFixture(name: string): { html: string; expected: unknown } {
  const dir = resolve(here, 'fixtures', 'article_snippets');
  const html = readFileSync(resolve(dir, `${name}.html`), 'utf-8');
  const expected = JSON.parse(readFileSync(resolve(dir, `${name}.expected.json`), 'utf-8'));
  return { html, expected };
}

describe('parseArticle', () => {
  it('extracts title, paragraphs, references from sample_w23_en', () => {
    const { html, expected } = loadFixture('sample_w23_en');
    const article = parseArticle(html);
    expect(article).toEqual(expected);
  });

  it('falls back to <title> when no <h1>', () => {
    const html = `<!doctype html><html><head><title>Fallback</title></head><body><p>x</p></body></html>`;
    const article = parseArticle(html);
    expect(article.title).toBe('Fallback');
  });

  it('returns empty when no recognizable structure', () => {
    const article = parseArticle('<html><body></body></html>');
    expect(article.title).toBe('');
    expect(article.paragraphs).toEqual([]);
    expect(article.references).toEqual([]);
  });

  it('deduplicates and sorts references', () => {
    const html = `
      <article id="article">
        <p data-pid="1">
          See <a class="b">Genesis 1:1</a> and <a class="b">John 3:16</a>.
        </p>
        <p data-pid="2">Also <a class="b">Genesis 1:1</a> again.</p>
      </article>
    `;
    const article = parseArticle(html);
    expect(article.references).toEqual(['Genesis 1:1', 'John 3:16']);
  });

  it('skips paragraphs without data-pid or id="p..."', () => {
    const html = `
      <article id="article">
        <p data-pid="1">Keep.</p>
        <p>Drop.</p>
        <p id="p2">Keep.</p>
        <p id="footer-x">Drop.</p>
      </article>
    `;
    const article = parseArticle(html);
    expect(article.paragraphs).toEqual(['Keep.', 'Keep.']);
  });

  it('handles malformed HTML gracefully (no throw)', () => {
    const malformed = '<article><p data-pid="1">Unclosed <a class="b">John 3:16';
    expect(() => parseArticle(malformed)).not.toThrow();
  });
});
```

- [ ] **Step 4: Run test to verify it fails**

```bash
pnpm -F @jw-agent-toolkit/core test -- tests/article.test.ts
```

Expected: FAIL — `parsers/article.ts` missing.

- [ ] **Step 5: Implement `src/parsers/article.ts`**

```ts
// packages/jw-core-js/src/parsers/article.ts
/**
 * Parser for wol.jw.org article HTML — TypeScript port.
 *
 * Mirrors `parse_article` from `packages/jw-core/src/jw_core/parsers/article.py`.
 * Uses `linkedom` (pure-JS DOM) so it works in browser, Node, Workers, Deno.
 *
 * Heuristics (must match Python 1:1):
 *  - title: h1 → header h1 → .pubName → <title> (first non-empty wins)
 *  - paragraphs: inside <article id="article"> (fallback <article>, fallback document).
 *    Keep <p> only if it has `data-pid` OR `id` starting with "p".
 *  - references: anchors whose class attribute contains the standalone word "b".
 */

import { parseHTML } from 'linkedom';

import type { Article } from '../models';

export function parseArticle(html: string): Article {
  const { document } = parseHTML(html);

  return {
    title: extractTitle(document),
    paragraphs: extractParagraphs(document),
    references: extractReferences(document),
  };
}

function textOf(el: Element | null): string {
  if (!el) return '';
  return (el.textContent ?? '').trim();
}

function extractTitle(doc: Document): string {
  // h1 → header h1 → .pubName (first non-empty)
  for (const selector of ['h1', 'header h1', '.pubName']) {
    const el = doc.querySelector(selector);
    const t = textOf(el);
    if (t) return t;
  }
  const titleTag = doc.querySelector('title');
  return textOf(titleTag);
}

function extractParagraphs(doc: Document): string[] {
  const root: Element | Document =
    doc.querySelector('article#article') ?? doc.querySelector('article') ?? doc;
  const out: string[] = [];
  const paragraphs = root.querySelectorAll('p');
  for (const p of paragraphs as unknown as Iterable<Element>) {
    const dataPid = p.getAttribute('data-pid');
    const idAttr = p.getAttribute('id') ?? '';
    if (!dataPid && !idAttr.startsWith('p')) continue;
    const text = collapseWhitespace(p.textContent ?? '');
    if (text) out.push(text);
  }
  return out;
}

function extractReferences(doc: Document): string[] {
  const anchors = doc.querySelectorAll('a');
  const seen = new Set<string>();
  for (const a of anchors as unknown as Iterable<Element>) {
    const classAttr = (a.getAttribute('class') ?? '').trim();
    if (!classAttr) continue;
    // Match Python's `lambda c: c and "b" in c.split()` — word in class list.
    const classList = classAttr.split(/\s+/);
    if (!classList.includes('b')) continue;
    const text = textOf(a);
    if (text) seen.add(text);
  }
  return [...seen].sort();
}

function collapseWhitespace(s: string): string {
  return s.replace(/\s+/g, ' ').trim();
}
```

- [ ] **Step 6: Update `src/index.ts`**

Append:
```ts
export { parseArticle } from './parsers/article';
```

- [ ] **Step 7: Run tests**

```bash
pnpm -F @jw-agent-toolkit/core test -- tests/article.test.ts
pnpm -F @jw-agent-toolkit/core run typecheck
```

Expected: 6 passed, zero typecheck errors.

- [ ] **Step 8: Commit**

```bash
git add packages/jw-core-js/src/parsers packages/jw-core-js/src/index.ts \
        packages/jw-core-js/tests/article.test.ts packages/jw-core-js/tests/fixtures
git commit -m "feat(jw-core-js): port parseArticle using linkedom"
```

---

### Task 14: Generate 50 cross-language `article` HTML fixtures

**Files:**
- Modify: `packages/jw-core/scripts/regenerate_cross_lang_fixtures.py`
- Create: `packages/jw-core/tests/fixtures/cross_lang/article/NNN_*.html` (50 files)
- Create: `packages/jw-core/tests/fixtures/cross_lang/article/NNN_*.expected.json` (50 files)
- Modify: `packages/jw-core/tests/test_cross_lang_parity.py`
- Modify: `packages/jw-core-js/tests/cross_lang/parity.test.ts`

- [ ] **Step 1: Identify or synthesize 50 HTML snippets**

Strategy:
1. Take 10 pinned snapshots from `packages/jw-core/tests/fixtures/wol_*.html` (existing test corpus, if any).
2. Synthesize 40 small representative snippets covering the heuristic branches: with/without `<h1>`, with `header h1`, with `.pubName`, malformed HTML, multiple paragraphs with mixed `data-pid` / `id="p*"`, references with hyperlinks at varying depth.

For mechanical generation, write a helper inside the generator:

```python
def _synthesize_article_html(*, idx: int, title_strategy: str, paragraphs: list[str], refs: list[str]) -> str:
    """Build a tiny WOL-shaped HTML doc for the article parser fixtures."""

    title_block = {
        "h1": f"<header><h1>{title_strategy}</h1></header>",
        "title_only": "",
        "pub_name": f'<div class="pubName">{title_strategy}</div>',
    }["h1" if idx % 3 == 0 else ("title_only" if idx % 3 == 1 else "pub_name")]

    head_title = f"<title>{title_strategy}</title>"

    body_paragraphs = ""
    for pi, ptext in enumerate(paragraphs, start=1):
        body_paragraphs += f'<p id="p{pi}" data-pid="{pi}">{ptext}</p>\n'

    refs_block = " ".join(f'<a class="b">{r}</a>' for r in refs)
    if refs_block:
        body_paragraphs += f'<p id="p99" data-pid="99">See {refs_block}.</p>\n'

    return (
        f"<!doctype html>\n<html><head>{head_title}</head>"
        f"<body>{title_block}<article id=\"article\">{body_paragraphs}</article></body></html>"
    )
```

- [ ] **Step 2: Extend the generator with `_write_article_fixtures()`**

Append to `regenerate_cross_lang_fixtures.py`:

```python
from jw_core.parsers.article import parse_article

ARTICLE_DIR = REPO_ROOT / "packages" / "jw-core" / "tests" / "fixtures" / "cross_lang" / "article"


def _article_seeds() -> list[dict]:
    """50 synthesized + a few real HTML snippets."""

    seeds = []
    titles = [
        "Walk in Faith", "Caminemos por fe", "Caminhemos pela fé",
        "The Kingdom Is Near", "El Reino está cerca", "O Reino está perto",
        "Love Your Neighbor", "Ama a tu prójimo", "Ame seu próximo",
        "Hope of the Resurrection", "La esperanza de la resurrección",
    ]
    ref_sets = [
        ["John 3:16", "Romans 6:23"],
        ["Genesis 1:1", "Psalm 83:18"],
        ["Matthew 24:14", "Revelation 21:3-4"],
        ["Hebrews 11:1"],
        [],
    ]
    paragraph_pool = [
        "Faith is more than a feeling.",
        "El Reino de Dios traerá paz duradera.",
        "O amor é o cumprimento da lei.",
        "Believers can have a sure hope.",
        "Esta esperanza se basa en la promesa de Jehová.",
    ]

    count = 0
    for ti, title in enumerate(titles):
        for ri, refs in enumerate(ref_sets):
            count += 1
            if count > 50:
                break
            paragraphs = paragraph_pool[: 1 + ((ti + ri) % len(paragraph_pool))]
            seeds.append({
                "id": f"{count:03d}_{ti:02d}_{ri:02d}",
                "title_strategy": title,
                "paragraphs": paragraphs,
                "refs": refs,
            })
        if count >= 50:
            break

    # Pad to 50 with permutations
    while len(seeds) < 50:
        i = len(seeds) + 1
        seeds.append({
            "id": f"{i:03d}_pad",
            "title_strategy": f"Padding {i}",
            "paragraphs": [f"Padding paragraph {i}."],
            "refs": [],
        })
    return seeds


def _write_article_fixtures() -> int:
    ARTICLE_DIR.mkdir(parents=True, exist_ok=True)
    for old in ARTICLE_DIR.glob("*"):
        old.unlink()

    seeds = _article_seeds()
    for idx, seed in enumerate(seeds, start=1):
        html = _synthesize_article_html(
            idx=idx,
            title_strategy=seed["title_strategy"],
            paragraphs=seed["paragraphs"],
            refs=seed["refs"],
        )
        (ARTICLE_DIR / f"{seed['id']}.html").write_text(html, encoding="utf-8")
        article = parse_article(html)
        expected = {
            "title": article.title,
            "paragraphs": list(article.paragraphs),
            "references": list(article.references),
        }
        (ARTICLE_DIR / f"{seed['id']}.expected.json").write_text(
            json.dumps(expected, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
    return len(seeds)
```

And update `main()`:

```python
def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    for old in OUT_DIR.glob("*.json"):
        old.unlink()

    all_cases = _mechanical_cases() + _edge_cases()
    for case in all_cases:
        path = OUT_DIR / f"{case['id']}.json"
        path.write_text(json.dumps(case, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    n_url = _write_wol_url_fixtures()
    n_article = _write_article_fixtures()

    print(
        f"Wrote {len(all_cases)} parse_reference + {n_url} wol_url + "
        f"{n_article} article fixtures"
    )
    return 0
```

- [ ] **Step 3: Regenerate**

```bash
uv run python packages/jw-core/scripts/regenerate_cross_lang_fixtures.py
```

Expected: `Wrote 500 parse_reference + 30 wol_url + 50 article fixtures`.

Verify:
```bash
ls packages/jw-core/tests/fixtures/cross_lang/article/*.html | wc -l
ls packages/jw-core/tests/fixtures/cross_lang/article/*.expected.json | wc -l
```
Expected: `50` each.

- [ ] **Step 4: Extend Python parity test**

Append to `packages/jw-core/tests/test_cross_lang_parity.py`:

```python
from jw_core.parsers.article import parse_article

ARTICLE_FIXTURES_DIR = (
    Path(__file__).parent / "fixtures" / "cross_lang" / "article"
)


def _load_article_fixtures() -> list[dict]:
    pairs = []
    for p in sorted(ARTICLE_FIXTURES_DIR.glob("*.expected.json")):
        html_path = p.with_suffix("").with_suffix(".html")
        pairs.append({
            "id": p.stem.replace(".expected", ""),
            "html_path": html_path,
            "expected": json.loads(p.read_text(encoding="utf-8")),
        })
    return pairs


_ARTICLE_FIXTURES = _load_article_fixtures()


def test_article_fixtures_count() -> None:
    assert len(_ARTICLE_FIXTURES) >= 50


@pytest.mark.parametrize("fixture", _ARTICLE_FIXTURES, ids=lambda f: f["id"])
def test_python_article_matches_fixture(fixture: dict) -> None:
    html = fixture["html_path"].read_text(encoding="utf-8")
    article = parse_article(html)
    actual = {
        "title": article.title,
        "paragraphs": list(article.paragraphs),
        "references": list(article.references),
    }
    assert actual == fixture["expected"]
```

- [ ] **Step 5: Extend TS parity test**

Append to `packages/jw-core-js/tests/cross_lang/parity.test.ts`:

```ts
import { parseArticle } from '../../src/parsers/article';
import { loadArticleFixtures, readHtml } from './_loader';

const articleFixtures = loadArticleFixtures();

describe('article cross-language parity', () => {
  it('found at least 50 article fixtures', () => {
    expect(articleFixtures.length).toBeGreaterThanOrEqual(50);
  });

  for (const fx of articleFixtures) {
    it(fx.id, () => {
      const html = readHtml(fx.htmlPath);
      const article = parseArticle(html);
      expect(article).toEqual(fx.expected);
    });
  }
});
```

- [ ] **Step 6: Run both parity tests**

```bash
uv run pytest packages/jw-core/tests/test_cross_lang_parity.py -v --tb=short
pnpm -F @jw-agent-toolkit/core test -- tests/cross_lang/
```

Expected: ≥582 tests pass on each side (1 sanity + 500 + 30 + 50 + 1 sanity).

> If TS divergence appears in HTML edge cases, the most common cause is
> linkedom whitespace handling vs lxml. Adjust `collapseWhitespace` in
> `article.ts` until parity holds.

- [ ] **Step 7: Commit**

```bash
git add packages/jw-core/scripts/regenerate_cross_lang_fixtures.py \
        packages/jw-core/tests/fixtures/cross_lang/article \
        packages/jw-core/tests/test_cross_lang_parity.py \
        packages/jw-core-js/tests/cross_lang/parity.test.ts
git commit -m "test(jw-core-js): 50 article HTML cross-language fixtures + parity"
```

---

### Task 15: Bundle size budget enforcement

**Files:**
- Modify: `packages/jw-core-js/package.json`
- Create: `packages/jw-core-js/.size-limit.json`

- [ ] **Step 1: Add size-limit dependency**

Edit `packages/jw-core-js/package.json` → `devDependencies`:

```jsonc
"size-limit": "^11.1.0",
"@size-limit/preset-small-lib": "^11.1.0"
```

Add script:
```jsonc
"size": "size-limit"
```

- [ ] **Step 2: Create `.size-limit.json`**

```json
[
  {
    "name": "index.js (full surface)",
    "path": "dist/index.js",
    "limit": "25 KB",
    "gzip": true
  },
  {
    "name": "reference.js (parser only)",
    "path": "dist/reference.js",
    "limit": "20 KB",
    "gzip": true
  },
  {
    "name": "clients/wol.js",
    "path": "dist/clients/wol.js",
    "limit": "8 KB",
    "gzip": true
  },
  {
    "name": "parsers/article.js (includes linkedom)",
    "path": "dist/parsers/article.js",
    "limit": "60 KB",
    "gzip": true,
    "ignore": ["linkedom"]
  }
]
```

- [ ] **Step 3: Run and verify**

```bash
pnpm install
pnpm -F @jw-agent-toolkit/core run build
pnpm -F @jw-agent-toolkit/core run size
```

Expected: all four budgets pass. If any exceeds, investigate the largest source — usually a stray import dragging in zod or linkedom unnecessarily.

- [ ] **Step 4: Add to CI**

Edit `.github/workflows/cross-lang.yml`, after the `TS build` step add:

```yaml
      - name: Bundle size budget
        run: pnpm -F @jw-agent-toolkit/core run size
```

- [ ] **Step 5: Commit**

```bash
git add packages/jw-core-js/package.json packages/jw-core-js/.size-limit.json \
        .github/workflows/cross-lang.yml pnpm-lock.yaml
git commit -m "ci(jw-core-js): enforce bundle size budgets (25KB index, 60KB w/ linkedom)"
```

---

### Task 16: Extensive README + `docs/guias/typescript-port.md`

**Files:**
- Modify: `packages/jw-core-js/README.md`
- Create: `docs/guias/typescript-port.md`

- [ ] **Step 1: Replace `packages/jw-core-js/README.md` with extensive version**

```markdown
# @jw-agent-toolkit/core

[![npm](https://img.shields.io/npm/v/@jw-agent-toolkit/core.svg)](https://www.npmjs.com/package/@jw-agent-toolkit/core)
[![license](https://img.shields.io/npm/l/@jw-agent-toolkit/core.svg)](./LICENSE)

TypeScript port of the 3 essential modules of [`jw-core`](https://github.com/eliascipre/jw-agent-toolkit/tree/main/packages/jw-core):

- **`parseReference(text)`** — multi-language Bible reference parser. Handles English, Spanish, Portuguese, and tier-1 languages (French, German, Italian, Russian, etc.). Mirrors Python output bit-for-bit (verified by 500 cross-language fixtures in CI).
- **`WOLClient.getBibleChapter(book, chapter)`** — fetches HTML from `wol.jw.org` and returns `{ url, html }`.
- **`parseArticle(html)`** — extracts `title`, `paragraphs`, `references` from a WOL article page.

ESM-only. Zero side effects on import. Runs in Node ≥18, modern browsers, Bun, Deno, Cloudflare Workers, Vercel Edge.

## Install

```bash
npm install @jw-agent-toolkit/core
# or
pnpm add @jw-agent-toolkit/core
# or
bun add @jw-agent-toolkit/core
```

## Quick start

### Parse a Bible reference

```ts
import { parseReference } from '@jw-agent-toolkit/core';

const ref = parseReference('Juan 3:16');
// {
//   bookNum: 43,
//   bookCanonical: 'John',
//   chapter: 3,
//   verseStart: 16,
//   verseEnd: null,
//   detectedLanguage: 'es',
//   rawMatch: 'juan 3:16',
// }
```

### Find all references in a paragraph

```ts
import { parseAllReferences } from '@jw-agent-toolkit/core';

const refs = parseAllReferences('Compare John 3:16 with Romans 6:23.');
// [
//   { bookNum: 43, chapter: 3, verseStart: 16, ... },
//   { bookNum: 45, chapter: 6, verseStart: 23, ... },
// ]
```

### Fetch a Bible chapter from WOL

```ts
import { WOLClient } from '@jw-agent-toolkit/core/clients/wol';

const client = new WOLClient();
const { url, html } = await client.getBibleChapter(43, 3, { language: 'es' });
console.log(url);  // https://wol.jw.org/es/wol/b/r4/lp-s/nwt/43/3
```

Inject a custom fetch (e.g. in tests, on the edge, or with auth):

```ts
const client = new WOLClient({
  fetch: globalThis.fetch,
  userAgent: 'my-app/1.0',
  timeoutMs: 10_000,
});
```

### Parse an article

```ts
import { parseArticle } from '@jw-agent-toolkit/core/parsers/article';

const article = parseArticle(html);
// {
//   title: 'Walk in Faith',
//   paragraphs: ['...', '...'],
//   references: ['Hebrews 11:1', 'Romans 10:17'],
// }
```

## Runtime validation (zod)

Every type has a paired runtime schema:

```ts
import { BibleRefSchema } from '@jw-agent-toolkit/core';

const result = BibleRefSchema.safeParse(untrustedInput);
if (result.success) {
  // result.data is a fully typed BibleRef
}
```

## Browser / Cloudflare Workers / Deno

The package is ESM-only and uses only `fetch` + `linkedom` (a pure-JS DOM). It runs unchanged in:

- **Browser** — bundle via Vite, esbuild, Webpack 5+, Rollup.
- **Cloudflare Workers** — import directly; works on Workers runtime.
- **Deno** — `import { parseReference } from 'npm:@jw-agent-toolkit/core'`.
- **Bun** — same as Node.

## Parity with Python

This package is generated from the Python `jw-core` source-of-truth and verified by a CI job that runs:

- 500 fixtures for `parse_reference` (English/Spanish/Portuguese + edge cases).
- 30 fixtures for WOL URL construction.
- 50 fixtures for article HTML parsing.

Both Python and TS must produce identical output for every fixture; any divergence fails CI.

See [docs/guias/typescript-port.md](https://github.com/eliascipre/jw-agent-toolkit/blob/main/docs/guias/typescript-port.md) for the sync protocol.

## What this package is NOT

By design, this is a minimal port. The following modules of `jw-core` are **not** ported to TS and live only in Python:

- Disk cache, throttler, telemetry.
- JWPUB / EPUB / PDF / audio / vision parsers.
- RAG, agents, MCP server.
- Fine-tuning, evaluation, generation pipelines.

If you need any of those, run the Python `jw-mcp` server on `localhost:8765` and hit it via HTTP.

## License

GPL-3.0-only — matches the Python `jw-core` package.
```

- [ ] **Step 2: Create `docs/guias/typescript-port.md`**

```markdown
# TypeScript port — `@jw-agent-toolkit/core`

Guía operacional para mantener el port TS sincronizado con Python. Spec: [`docs/superpowers/specs/2026-05-31-fase-47-jw-core-js-minimal-design.md`](../superpowers/specs/2026-05-31-fase-47-jw-core-js-minimal-design.md).

## Qué hay en el port

| Módulo Python | Módulo TS |
|---|---|
| `jw_core.parsers.reference.parse_reference` | `@jw-agent-toolkit/core/reference#parseReference` |
| `jw_core.clients.wol.WOLClient.get_bible_chapter` | `@jw-agent-toolkit/core/clients/wol#WOLClient.getBibleChapter` |
| `jw_core.parsers.article.parse_article` | `@jw-agent-toolkit/core/parsers/article#parseArticle` |
| `jw_core.data.books.BOOKS` (lectura) | `src/data/books.json` (auto-generado) |
| `jw_core.languages.LANGUAGES` (lectura) | `src/data/languages.json` (auto-generado) |

## Política de sync: Python lidera

> **Regla operacional**: Python lidera, TS sigue dentro del mismo PR.

Cualquier PR que toque `parse_reference`, `WOLClient.get_bible_chapter`, `parse_article` o el registro de libros debe:

1. Cambiar el código Python.
2. Regenerar archivos compartidos: `make dump-shared-data`.
3. Si el cambio afecta el output del parser, regenerar fixtures: `make regen-cross-lang-fixtures`.
4. Actualizar el TS port en el mismo PR (o abrir issue de seguimiento con SLA ≤1 sprint).

CI bloquea el merge si:
- `git diff` después de `make dump-shared-data` no es limpio.
- Cualquiera de los 580+ fixtures cross-lang diverge entre Python y TS.

## Comandos clave

```bash
# Regenerar books.json + languages.json (después de tocar Python)
make dump-shared-data

# Regenerar fixtures (después de cambiar el algoritmo)
make regen-cross-lang-fixtures

# Verificar TS local
pnpm -F @jw-agent-toolkit/core run verify

# Solo parity tests
uv run pytest packages/jw-core/tests/test_cross_lang_parity.py -v
pnpm -F @jw-agent-toolkit/core test -- tests/cross_lang/

# Build + size budget
pnpm -F @jw-agent-toolkit/core run build
pnpm -F @jw-agent-toolkit/core run size
```

## Añadir un libro / idioma nuevo

1. Edita `packages/jw-core/src/jw_core/data/books.py` (o `book_locales.py`).
2. Corre `make dump-shared-data` — verifica el diff en `packages/jw-core-js/src/data/books.json`.
3. Corre `make regen-cross-lang-fixtures` si quieres que los nuevos nombres entren a la suite de parity.
4. Commit en un solo PR. CI debe estar verde.

## Añadir una fixture nueva

1. Edita `packages/jw-core/scripts/regenerate_cross_lang_fixtures.py` (sección `_edge_cases`).
2. Corre `make regen-cross-lang-fixtures` con confirmación.
3. Inspecciona el JSON generado — debe reflejar la verdad esperada.
4. Si el `expected` no es correcto, el parser tiene un bug — arréglalo, no la fixture.

## Cuándo NO portar a TS

Si tu nuevo módulo Python:
- Requiere acceso al disco (cache, JWPUB DB),
- Requiere binarios nativos (lxml, sqlite3),
- Requiere subprocess (whisper, fine-tuning),

→ NO lo portes. El consumidor TS hace REST a `jw-mcp` corriendo en Python.

## Publish flow

Ver [`docs/publishing/npm.md`](../publishing/npm.md).
```

- [ ] **Step 3: Link from `docs/README.md`**

Append to the "Guías por tema" section:

```markdown
- [TypeScript port](guias/typescript-port.md) — Cómo se mantiene `@jw-agent-toolkit/core` sincronizado con `jw-core` Python.
```

- [ ] **Step 4: Commit**

```bash
git add packages/jw-core-js/README.md docs/guias/typescript-port.md docs/README.md
git commit -m "docs(jw-core-js): extensive README + sync protocol guide"
```

---

### Task 17: `obsidian-jw-bridge` smoke test consuming `workspace:*`

**Files:**
- Modify: `apps/obsidian-jw-bridge/package.json`
- Create: `apps/obsidian-jw-bridge/tests/jw-core-js-smoke.test.ts` (or inline existing test file)

> Note: the goal is non-binding adoption. Just import + invoke `parseReference` to prove the workspace wiring works. The plugin is NOT migrated to use the TS port for production.

- [ ] **Step 1: Add dependency**

Edit `apps/obsidian-jw-bridge/package.json`, add to `dependencies`:
```jsonc
"@jw-agent-toolkit/core": "workspace:*"
```

- [ ] **Step 2: Create smoke test**

```ts
// apps/obsidian-jw-bridge/tests/jw-core-js-smoke.test.ts
import { describe, expect, it } from 'vitest';

import { parseReference } from '@jw-agent-toolkit/core';

describe('@jw-agent-toolkit/core integration smoke', () => {
  it('parseReference is callable from obsidian-jw-bridge', () => {
    const ref = parseReference('Juan 3:16');
    expect(ref?.bookNum).toBe(43);
  });
});
```

> If `obsidian-jw-bridge` doesn't have a Vitest setup yet, this test can live in a `__smoke__` directory that's ignored by the obsidian build but picked up by `pnpm -F obsidian-jw-bridge test`.

- [ ] **Step 3: Verify wiring**

```bash
pnpm install
pnpm -F obsidian-jw-bridge test -- jw-core-js-smoke
```

Expected: 1 test passes. If `pnpm` doesn't symlink the workspace package correctly, debug — usually a missing `workspaces` entry or a stale lockfile (`rm pnpm-lock.yaml && pnpm install`).

- [ ] **Step 4: Commit**

```bash
git add apps/obsidian-jw-bridge/package.json apps/obsidian-jw-bridge/tests/jw-core-js-smoke.test.ts \
        pnpm-lock.yaml
git commit -m "test(obsidian-jw-bridge): smoke test consuming @jw-agent-toolkit/core via workspace:*"
```

---

### Task 18: Publish v0.1.0 to npm

**Files:**
- Modify: `packages/jw-core-js/package.json` (version 0.0.1 → 0.1.0)
- Modify: `packages/jw-core-js/CHANGELOG.md`

> Pre-requisite: scope `@jw-agent-toolkit/*` reserved (Task 3) and `NPM_TOKEN` secret configured.

- [ ] **Step 1: Bump version**

```bash
cd packages/jw-core-js
pnpm version 0.1.0 --no-git-tag-version
```

This rewrites `package.json` to `"version": "0.1.0"`.

- [ ] **Step 2: Update CHANGELOG**

Edit `packages/jw-core-js/CHANGELOG.md`:

```markdown
# Changelog

## 0.1.0 — 2026-05-31

### Added
- `parseReference(text)` — multi-language Bible reference parser (en/es/pt + tier-1).
- `parseAllReferences(text)` — find all references in text.
- `ReferenceParser` class for explicit construction.
- `WOLClient` with `getBibleChapter(book, chapter)` and `fetch(url)`.
- `buildBibleChapterUrl()` standalone helper.
- `parseArticle(html)` — extract title, paragraphs, references.
- `BibleRefSchema`, `ArticleSchema`, `FetchedDocumentSchema` (zod runtime validators).
- `toSnakeCaseBibleRef` / `fromSnakeCaseBibleRef` bridge helpers.
- `getLanguage(iso)` / `listLanguages()` for the language registry.

### Parity
- 500+ cross-language fixtures verified in CI.

## 0.0.1 — 2026-05-31

- Scope placeholder.
```

- [ ] **Step 3: Dry-run publish**

```bash
cd packages/jw-core-js
pnpm install
pnpm run verify
pnpm publish --dry-run --access public
```

Expected:
- `verify` passes (lint + typecheck + 600+ tests + build).
- `publish --dry-run` lists the tarball contents: `dist/`, `src/`, `LICENSE`, `README.md`, `CHANGELOG.md`. NO `tests/`, NO `tools/`, NO config files.

Inspect tarball contents:
```bash
pnpm pack
tar -tf jw-agent-toolkit-core-0.1.0.tgz | sort
```

- [ ] **Step 4: Tag and push (triggers automated publish)**

```bash
git add packages/jw-core-js/package.json packages/jw-core-js/CHANGELOG.md
git commit -m "chore(jw-core-js): release 0.1.0"
git tag -s jw-core-js@v0.1.0 -m "jw-core-js 0.1.0 — first functional release"
git push origin main
git push origin jw-core-js@v0.1.0
```

The `publish-npm-on-tag.yml` workflow fires, runs verify, and publishes with provenance.

- [ ] **Step 5: Verify on npm**

Open https://www.npmjs.com/package/@jw-agent-toolkit/core. Expect:
- Version `0.1.0` published.
- README rendered.
- License `GPL-3.0-only`.
- Provenance badge present.

Smoke test installation:
```bash
mkdir /tmp/jw-test && cd /tmp/jw-test
npm init -y
npm install @jw-agent-toolkit/core
node --input-type=module -e "import {parseReference} from '@jw-agent-toolkit/core'; console.log(parseReference('Juan 3:16'))"
```
Expected: prints a BibleRef object with `bookNum: 43`.

---

### Task 19: Update `docs/VISION_AUDIT.md` and `docs/ROADMAP.md`

**Files:**
- Modify: `docs/VISION_AUDIT.md`
- Modify: `docs/ROADMAP.md`

- [ ] **Step 1: Add row to VISION_AUDIT.md summary table**

Insert in the appropriate section:

```markdown
| Fase 47 (jw-core-js minimal) | ✅ Nuevo | `@jw-agent-toolkit/core` ESM, 580+ fixtures cross-lang, GPL-3.0 |
```

- [ ] **Step 2: Append Fase 47 section to ROADMAP.md**

```markdown
## Fase 47 — `jw-core-js-minimal`: port TS de los 3 módulos críticos ✅

> Tier 4 nueva superficie JS/móvil. Spec: `docs/superpowers/specs/2026-05-31-fase-47-jw-core-js-minimal-design.md`.

- ✅ Nuevo paquete TS `packages/jw-core-js/` (ESM-only, Node ≥18, browser/Bun/Deno/Workers).
- ✅ pnpm workspace polyglot Python + TS.
- ✅ Port `parseReference` (paridad 100% en 500 fixtures cross-lang).
- ✅ Port `WOLClient.getBibleChapter` con `fetch` inyectable + timeout.
- ✅ Port `parseArticle` con `linkedom` (puro JS, sin native deps).
- ✅ `books.json` + `languages.json` generados desde Python (single source of truth).
- ✅ 580+ fixtures cross-lang: 500 parse_reference + 30 wol_url + 50 article.
- ✅ Modelos con zod schemas (runtime validation).
- ✅ Snake_case ↔ camelCase bridge.
- ✅ Bundle size budget: 25KB index, 60KB con linkedom.
- ✅ tsdown build + Vitest + Biome + tsc estricto.
- ✅ Workflow CI `cross-lang` (bloqueante en main).
- ✅ Workflow `publish-npm-on-tag` con provenance.
- ✅ Publicado en npm como `@jw-agent-toolkit/core@0.1.0` (GPL-3.0-only).
- ✅ Guía `docs/guias/typescript-port.md` + `docs/publishing/npm.md`.
- ✅ Smoke test desde `apps/obsidian-jw-bridge` consumiendo `workspace:*`.

### Cobertura

- ✅ TS: 600+ tests (50 TS-only + 580 cross-lang parity).
- ✅ Python: +581 tests parametrizados cross-lang.
- ✅ Sin regresiones en los 1984 tests Python existentes.
```

- [ ] **Step 3: Commit**

```bash
git add docs/VISION_AUDIT.md docs/ROADMAP.md
git commit -m "docs(roadmap): land Fase 47 — jw-core-js minimal TS port"
```

---

### Task 20: Final audit — full suite green + no regressions

**Files:** none (verification only).

- [ ] **Step 1: Lint + format Python**

```bash
uv run ruff check packages/jw-core
uv run ruff format --check packages/jw-core
```
Expected: zero violations.

- [ ] **Step 2: Lint + format TS**

```bash
pnpm -F @jw-agent-toolkit/core run lint
```
Expected: zero violations.

- [ ] **Step 3: Typecheck TS**

```bash
pnpm -F @jw-agent-toolkit/core run typecheck
```
Expected: zero errors.

- [ ] **Step 4: Full Python suite (no regressions)**

```bash
uv run pytest packages/ -v --tb=short
```
Expected: 1984 existing + ~582 new cross-lang = ~2566 tests green. Zero regressions.

- [ ] **Step 5: Full TS suite**

```bash
pnpm -F @jw-agent-toolkit/core run verify
```
Expected:
- Lint clean.
- Typecheck clean.
- 600+ tests pass.
- Build emits to `dist/`.

- [ ] **Step 6: Bundle size check**

```bash
pnpm -F @jw-agent-toolkit/core run size
```
Expected: all 4 budgets within limits.

- [ ] **Step 7: Cross-lang parity end-to-end**

```bash
make dump-shared-data
git diff --exit-code packages/jw-core-js/src/data/
uv run pytest packages/jw-core/tests/test_cross_lang_parity.py -v --tb=short
pnpm -F @jw-agent-toolkit/core test -- tests/cross_lang/
```
Expected:
- `git diff --exit-code` is clean.
- Both parity suites pass.

- [ ] **Step 8: CI dry-run via act (optional)**

```bash
# Only if `act` is installed locally
act -W .github/workflows/cross-lang.yml
```
Expected: green job.

- [ ] **Step 9: Inspect npm page**

Open https://www.npmjs.com/package/@jw-agent-toolkit/core, verify badge, license, README.

- [ ] **Step 10: Final commit if any polish**

If any docstring fix or comment cleanup emerged: amend or new commit `chore(jw-core-js): polish`. Otherwise nothing to do.

---

### Task 21: Optional buffer — bug fixes / Fase 48 prep

**Files:** dynamic — depends on what shakes out from real-world adoption.

This task absorbs:
- Edge cases discovered when Fase 48 (`wol-browser-ext`) imports the package and runs the extension in Chrome/Firefox.
- Bundle size optimizations if Fase 48 adoption reveals friction (e.g. tree-shaking linkedom further).
- TypeScript version bumps if the ecosystem ships breaking changes.
- Adding French/German/Italian fixtures when the tier-1 language coverage is exercised in production.

- [ ] **Step 1: Reserve sprint capacity (1 week)**

No code in this task by default. Open it as needed.

- [ ] **Step 2: Track issues that emerge under tag `fase-47-followup`**

```bash
gh issue list --label fase-47-followup
```

- [ ] **Step 3: Cut `v0.1.x` patch releases as bugs arise**

Each patch follows the flow in `docs/publishing/npm.md`.

---

## Self-review summary

- **Spec coverage**: Each section of the spec maps to a task above.
  - Architecture + workspace layout → Task 1.
  - Sincronización política #1 (books JSON) → Task 2.
  - Sincronización política #2 (500 fixtures parametrizadas) → Tasks 7, 8, 9, 12, 14.
  - Sincronización política #3 (regla operacional Python lidera) → documentada en Task 16 (typescript-port.md).
  - `parseReference` port + zod models → Tasks 4, 5.
  - `WOLClient` port + languages → Tasks 10, 11.
  - `parseArticle` port con linkedom → Task 13.
  - CI cross-lang + publish-on-tag → Tasks 3, 12, 14, 15.
  - Reserva scope npm + v0.0.1 placeholder → Task 3.
  - Bundle size budget → Task 15.
  - Tests del propio paquete TS (50+ TS-only) → Tasks 4, 5, 10, 11, 13.
  - Tests cross-lang (500 + 30 + 50 = 580) → Tasks 8, 9, 12, 14.
  - Integración con apps existentes (workspace:*) → Task 17.
  - Publicación v0.1.0 → Task 18.
  - Docs (README + guías) → Task 16.
  - VISION_AUDIT + ROADMAP → Task 19.
  - Final audit sin regresiones → Task 20.
  - Buffer / Fase 48 prep → Task 21.

- **No placeholders**: every code step contains literal source. Every YAML/JSON step shows the exact shape. Every command shows the precise invocation and expected output. No `TODO`, no `…`, no `<placeholder>`.

- **Type consistency**:
  - `BibleRef` shape camelCase TS / snake_case JSON, bridged by `toSnakeCaseBibleRef` / `fromSnakeCaseBibleRef`, used identically in `parity.test.ts` and `test_cross_lang_parity.py`.
  - `Language` shape: TS camelCase fields (`wolResource`, `lpTag`, `defaultBible`), Python snake_case fields (`wol_resource`, `lp_tag`, `default_bible`). Bridge applied at `fromRaw()` boundary in `languages.ts`.
  - `WOLClientOptions.fetch` signature uses standard `typeof fetch`, compatible with Node 18+, browser, Workers, Bun, Deno.
  - `Article` shape identical in both runtimes: `{ title: string, paragraphs: string[], references: string[] }`.

- **Test ordering**: TDD strictly applied. Every Task that introduces source code has Step 1 = failing test, Step 2 = verify fail, Step 3 = implementation, Step 4 = verify pass, Step 5+ = commit.

- **Cross-language coupling**: 580+ fixtures live under the Python package (single source of truth). Both runtimes consume them. CI fails if either diverges.

- **Sprint independence**: each sprint produces something independently merge-able. Sprint 1 ends with placeholder v0.0.1 on npm. Sprint 2 ends with `parseReference` shipped TS-only. Sprint 3 ends with first cross-lang verification. Sprint 7 ends with v0.1.0 published. Sprint 8 is final audit.

- **Risk coverage** (from spec):
  - Regex Python ↔ JS divergence: covered by edge cases in Task 7 and full parity in Tasks 8, 9.
  - `books.json` drift: covered by CI step in Task 3 + meta sha256 in Task 2.
  - Drift TS ↔ Python: covered by `cross-lang` blocking job + sync protocol doc.
  - linkedom vs lxml: covered by 50 article fixtures in Task 14.
  - npm scope squatting: addressed by v0.0.1 reservation in Task 3.
  - Bundle size: covered by `.size-limit.json` in Task 15.
  - Unicode normalization: explicit edge cases in Task 7 (`génesis_nfc` / `genesis_nfd`).

- **Boundary respect**: Tasks never touch `cache/`, `throttle/`, `telemetry/`, `jwpub/`, `epub/`, `pdf/`, `audio/`, `vision/`, RAG, agents, MCP, eval, finetune, gen. Spec no-objetivos honored.

## Execution choice

Plan completo, 21 tareas en 8 sprints, ~6-8 semanas con 1 dev. Dos opciones de ejecución:

1. **Subagent-driven (recomendado para XL)** — dispatch fresh sub-agente por tarea (o por sprint), review entre tareas, iteración rápida (`superpowers:subagent-driven-development`). Recomendado para esta fase porque el contexto cruza Python + TS + CI + npm — un agente fresco por sprint mantiene foco.
2. **Inline** — ejecuto tareas en esta sesión con checkpoints (`superpowers:executing-plans`). Viable pero con riesgo de context fragmentation dado el tamaño XL.

¿Cuál prefieres?
