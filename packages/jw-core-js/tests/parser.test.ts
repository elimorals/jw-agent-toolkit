/**
 * Parser tests anchored on the shared golden fixture.
 *
 * The same JSON is consumed by `packages/jw-core/tests/test_golden_fixture_parity.py`
 * so a Python ↔ TypeScript drift will surface on either side.
 */

import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { resolve, dirname } from "node:path";
import { describe, expect, it } from "vitest";

import { parseReference, parseAllReferences, BibleRef } from "../src/index.js";

const HERE = dirname(fileURLToPath(import.meta.url));
const FIXTURE = resolve(HERE, "..", "..", "..", "shared", "data", "bible_references_golden.json");

interface Case {
  input: string;
  book_num: number;
  book_canonical: string;
  chapter: number;
  verse_start: number | null;
  verse_end: number | null;
  language: string;
}

const fixture = JSON.parse(readFileSync(FIXTURE, "utf-8")) as {
  cases: Case[];
};

describe("parseReference against shared golden fixture", () => {
  for (const c of fixture.cases) {
    it(`parses "${c.input}" (${c.language})`, () => {
      const ref = parseReference(c.input);
      expect(ref, `expected a match for ${c.input}`).not.toBeNull();
      const r = ref as BibleRef;
      expect(r.bookNum).toBe(c.book_num);
      expect(r.bookCanonical).toBe(c.book_canonical);
      expect(r.chapter).toBe(c.chapter);
      expect(r.verseStart).toBe(c.verse_start);
      expect(r.verseEnd).toBe(c.verse_end);
    });
  }
});

describe("parseAllReferences", () => {
  it("finds multiple refs in one paragraph", () => {
    const refs = parseAllReferences(
      "Compare Juan 3:16 with 1 Corintios 13:4-7 and Salmos 23:1.",
    );
    expect(refs).toHaveLength(3);
    expect(refs[0]?.bookCanonical).toBe("John");
    expect(refs[1]?.bookCanonical).toBe("1 Corinthians");
    expect(refs[2]?.bookCanonical).toBe("Psalms");
  });

  it("returns [] for empty input", () => {
    expect(parseAllReferences("")).toEqual([]);
  });

  it("returns [] when no Bible-like text is present", () => {
    expect(parseAllReferences("just some prose, no references here")).toEqual([]);
  });
});

describe("parseReference resolves abbreviations", () => {
  it("Mt 5:7 → Matthew", () => {
    const r = parseReference("Mt 5:7");
    expect(r?.bookCanonical).toBe("Matthew");
  });
  it("Heb 11:1 → Hebrews", () => {
    const r = parseReference("Heb 11:1");
    expect(r?.bookCanonical).toBe("Hebrews");
  });
  it("Ap 21:4 → Revelation (es abbr)", () => {
    const r = parseReference("Ap 21:4");
    expect(r?.bookCanonical).toBe("Revelation");
  });
});

describe("longest-first alternation", () => {
  it("'1 Corintios' matches before bare 'Corintios'", () => {
    const r = parseReference("1 Corintios 13:4");
    expect(r?.bookCanonical).toBe("1 Corinthians");
    expect(r?.chapter).toBe(13);
  });

  it("'2 Pedro' matches before bare 'Pedro'", () => {
    const r = parseReference("2 Pedro 1:5");
    expect(r?.bookCanonical).toBe("2 Peter");
  });
});
