# @jw-agent-toolkit/core

Minimal TypeScript port of [`jw-core`](../jw-core) (Python). MVP scope for
**Fase 47** — only the surface a browser extension or a Capacitor app
needs to parse Bible references and build canonical WOL URLs client-side.

## Install

```bash
npm install @jw-agent-toolkit/core
```

## Use

```ts
import {
  parseReference,
  parseAllReferences,
  toCanonical,
  displayName,
} from "@jw-agent-toolkit/core";

const ref = parseReference("Juan 3:16");
// ref?.bookCanonical === "John"
// ref?.chapter === 3
// ref?.verseStart === 16
// ref?.wolUrl("es") === "https://wol.jw.org/es/wol/b/r4/lp-s/nwt/43/3#study=discover&v=43:3:16"

const refs = parseAllReferences("Compare Juan 3:16 with 1 Corintios 13:4-7.");
// refs.length === 2

// Fase 46 versification mapping
const result = toCanonical({
  book: "Joel",
  bookNum: 29,
  chapter: 2,
  verseStart: 28,
  verseEnd: 32,
  fromTradition: "nwt",
  toTradition: "masoretic",
});
// result.coord === { chapter: 3, verseStart: 1, verseEnd: 5 }
// result.isDiscrepant === true
```

## Public API

| Surface | What it does |
|---|---|
| `parseReference(text)` | First Bible ref in the string, or `null` |
| `parseAllReferences(text)` | Every Bible ref in the string |
| `ReferenceParser` | Constructable parser (testing / advanced use) |
| `BibleRef` | Class with `display()`, `wolUrl(lang, pub?)`, `toJSON()` |
| `BOOKS`, `canonicalName`, `displayName` | 66-book table en/es/pt |
| `getLanguageConfig(lang)` | `{iso, wolResource, lpTag, defaultBible}` |
| `toCanonical(args)` | Map between nwt/masoretic/lxx/vulgate |
| `explain(args)` | Trilingual rationale for a discrepancy |
| `loadCatalog()` | All versification entries |

## Parity with Python

The shared JSON fixture
[`shared/data/bible_references_golden.json`](../../shared/data/bible_references_golden.json)
is the contract. Both implementations run it in CI:

- TypeScript: `packages/jw-core-js/tests/parser.test.ts` (Vitest)
- Python: `packages/jw-core/tests/test_golden_fixture_parity.py` (pytest)

A drift on either side fails the corresponding suite. The Python source
of truth for the 66-book table is `packages/jw-core/src/jw_core/data/books.py`;
`packages/jw-core-js/src/books.json` is regenerated from it whenever a new
language or alias is added.

## What is NOT in v0.1 MVP

This release is intentionally narrow. The deliberately deferred surfaces:

| Area | Status | Where it lives in Python |
|---|---|---|
| `parse_verse`, `parse_verses` | Not ported | `jw_core.parsers.verse` |
| `parse_article` | Not ported | `jw_core.parsers.article` |
| `parse_study_notes` | Not ported | `jw_core.parsers.study_notes` |
| `parse_cross_references` | Not ported | `jw_core.parsers.study_notes` |
| WOL / CDN / TopicIndex HTTP clients | Not ported | `jw_core.clients.*` |
| JWPUB / EPUB parsers (AES-128 decrypt) | Not ported | `jw_core.parsers.jwpub`, `epub` |
| Cache, throttle, telemetry | Not ported | `jw_core.cache`, `throttle`, `telemetry` |
| Provenance models | Not ported | `jw_core.provenance` |
| `BibleRef.tradition` field | Not ported | `jw_core.models.BibleRef` |
| Multi-locale beyond en/es/pt | Not ported | `jw_core.data.book_locales` |

## Build + test locally

```bash
cd packages/jw-core-js
npm install
npm test        # vitest (40 tests today)
npm run build   # tsup → dist/{index,books,versification}.{js,cjs,d.ts}
npm run typecheck
```

## License

GPL-3.0-only. Same as the rest of the monorepo.
