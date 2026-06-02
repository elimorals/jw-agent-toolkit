/**
 * Canonical 66-book table with names in en/es/pt.
 *
 * Mirrors the Python `jw_core.data.books.BOOKS` registry. The fixture
 * `shared/data/bible_books.json` is generated from the Python source and a
 * parity test (`packages/jw-core/tests/test_golden_fixture_parity.py`)
 * locks both sides to the same data.
 *
 * To extend to a new language, add a top-level `languages` entry and append
 * an array of preferred + alternative names to each book. The parser
 * automatically picks up additional language keys without code changes.
 */

import bookData from "./books.json" with { type: "json" };

export type Language = "en" | "es" | "pt";

export interface BookEntry {
  num: number;
  canonical: string;
  names: Partial<Record<Language, readonly string[]>>;
}

export interface BookCatalog {
  version: string;
  languages: readonly Language[];
  books: readonly BookEntry[];
}

export const BOOKS: readonly BookEntry[] = (
  bookData as BookCatalog
).books as readonly BookEntry[];

export const CATALOG_VERSION: string = (bookData as BookCatalog).version;

/** Lookup the canonical English name for a book number (1..66). */
export function canonicalName(bookNum: number): string | undefined {
  return BOOKS.find((b) => b.num === bookNum)?.canonical;
}

/** Lookup the preferred display name in a target language. */
export function displayName(
  bookNum: number,
  lang: Language = "en",
): string | undefined {
  const book = BOOKS.find((b) => b.num === bookNum);
  if (!book) return undefined;
  const list = book.names[lang];
  if (list && list.length > 0) return list[0];
  const en = book.names.en;
  if (en && en.length > 0) return en[0];
  return book.canonical;
}
