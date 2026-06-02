/**
 * Multi-language Bible reference parser.
 *
 * Port of `jw_core.parsers.reference.ReferenceParser`. Builds a single
 * regex from every book name + alias across en/es/pt and runs it against
 * a normalized copy of the input. Sorting alternatives by length DESC
 * guarantees that "1 Corintios" is matched before "Corintios".
 */

import { BOOKS } from "./books.js";
import type { Language } from "./books.js";
import { BibleRef } from "./BibleRef.js";
import { escapeRegex, norm, normKey } from "./normalize.js";

interface IndexEntry {
  bookNum: number;
  language: Language;
  canonical: string;
}

let cachedParser: ReferenceParser | null = null;

export class ReferenceParser {
  private readonly index: Map<string, IndexEntry> = new Map();
  private readonly regex: RegExp;

  constructor() {
    const displayForms = new Set<string>();

    for (const book of BOOKS) {
      for (const [langKey, names] of Object.entries(book.names) as Array<
        [Language, readonly string[] | undefined]
      >) {
        if (!names) continue;
        for (const name of names) {
          const display = norm(name).trim();
          const key = normKey(name);
          if (!key) continue;
          if (!this.index.has(key)) {
            this.index.set(key, {
              bookNum: book.num,
              language: langKey,
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
    const ordered = [...displayForms].sort((a, b) => b.length - a.length);
    const alternatives = ordered.map((form) =>
      form
        .split(" ")
        .map((part) => escapeRegex(part))
        .join("\\s+"),
    );
    const bookAlt = alternatives.join("|");
    const pattern =
      `\\b(?<book>${bookAlt})\\s*` +
      `(?<chapter>\\d+)` +
      `(?:\\s*[:.]\\s*(?<verse_start>\\d+)` +
      `(?:\\s*[\\-\\u2013\\u2014]\\s*(?<verse_end>\\d+))?)?`;
    return new RegExp(pattern, "giu");
  }

  parse(text: string): BibleRef[] {
    if (!text) return [];
    const normalized = norm(text);
    const refs: BibleRef[] = [];

    // Reset the regex lastIndex between calls (sticky/global pitfall).
    this.regex.lastIndex = 0;
    let match: RegExpExecArray | null;
    while ((match = this.regex.exec(normalized)) !== null) {
      const groups = match.groups ?? {};
      const bookMatch = groups["book"];
      if (!bookMatch) continue;
      const key = normKey(bookMatch);
      const entry = this.index.get(key);
      if (!entry) continue;
      const chapterStr = groups["chapter"];
      if (!chapterStr) continue;
      const chapter = Number.parseInt(chapterStr, 10);
      if (!Number.isFinite(chapter) || chapter < 1) continue;
      const verseStartStr = groups["verse_start"];
      const verseEndStr = groups["verse_end"];
      const verseStart =
        verseStartStr != null ? Number.parseInt(verseStartStr, 10) : null;
      const verseEnd =
        verseEndStr != null ? Number.parseInt(verseEndStr, 10) : null;
      try {
        refs.push(
          new BibleRef({
            bookNum: entry.bookNum,
            bookCanonical: entry.canonical,
            chapter,
            verseStart: verseStart != null && verseStart > 0 ? verseStart : null,
            verseEnd: verseEnd != null && verseEnd > 0 ? verseEnd : null,
            detectedLanguage: entry.language,
            rawMatch: normalized.slice(match.index, match.index + match[0].length).trim(),
          }),
        );
      } catch {
        // The Python parser silently skips ValidationError; mirror that.
        continue;
      }
    }
    return refs;
  }

  parseOne(text: string): BibleRef | null {
    const refs = this.parse(text);
    return refs.length > 0 ? (refs[0] as BibleRef) : null;
  }
}

function singleton(): ReferenceParser {
  if (cachedParser == null) {
    cachedParser = new ReferenceParser();
  }
  return cachedParser;
}

/** Parse the first Bible reference in `text`. Returns null if no match. */
export function parseReference(text: string): BibleRef | null {
  return singleton().parseOne(text);
}

/** Parse every Bible reference in `text`. */
export function parseAllReferences(text: string): BibleRef[] {
  return singleton().parse(text);
}
