/**
 * @jw-agent-toolkit/core — minimal TypeScript port of jw-core.
 *
 * Public surface (MVP, v0.1):
 *   parseReference(text)          — first Bible ref in `text` or null
 *   parseAllReferences(text)      — every Bible ref in `text`
 *   BibleRef                       — structured Bible reference + display + wolUrl
 *   BOOKS, canonicalName, displayName  — 66-book table in en/es/pt
 *   getLanguageConfig(lang)        — WOL URL building blocks per language
 *   toCanonical(...)               — Fase 46 numbering tradition mapper
 *   explain(...)                   — trilingual rationale for a discrepancy
 *   loadCatalog(), CATALOG_VERSION — versification catalog accessors
 *
 * Not yet ported (see docs/guias/jw-core-js.md):
 *   - Parsers for verse, study notes, articles, cross references
 *   - HTTP clients (WOL / CDN / TopicIndex)
 *   - Locale catalog beyond en/es/pt
 *   - Cache, throttle, telemetry primitives
 *   - Provenance models
 */

export { parseReference, parseAllReferences, ReferenceParser } from "./parser.js";
export { BibleRef, langFromWolPath } from "./BibleRef.js";
export type { BibleRefInput } from "./BibleRef.js";
export {
  BOOKS,
  CATALOG_VERSION as BOOKS_VERSION,
  canonicalName,
  displayName,
} from "./books.js";
export type { Language, BookEntry, BookCatalog } from "./books.js";
export { getLanguageConfig } from "./languages.js";
export type { LanguageConfig } from "./languages.js";
export {
  toCanonical,
  explain,
  loadCatalog,
  CATALOG_VERSION as VERSIFICATION_VERSION,
} from "./versification.js";
export type {
  Tradition,
  VersificationIssue,
  VerseCoord,
  VersificationEntry,
  MappingResult,
  ToCanonicalArgs,
} from "./versification.js";
