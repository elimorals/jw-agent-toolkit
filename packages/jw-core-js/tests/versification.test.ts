import { describe, expect, it } from "vitest";

import { explain, loadCatalog, toCanonical } from "../src/index.js";

describe("loadCatalog", () => {
  it("ships the same Fase 46 seed entries", () => {
    const entries = loadCatalog();
    expect(entries.length).toBeGreaterThanOrEqual(25);
    for (const entry of entries) {
      expect(entry.explanation.en).toBeTruthy();
      expect(entry.explanation.es).toBeTruthy();
      expect(entry.explanation.pt).toBeTruthy();
    }
  });

  it("is cached (referential identity across calls)", () => {
    expect(loadCatalog()).toBe(loadCatalog());
  });
});

describe("toCanonical", () => {
  it("identity when fromTradition === toTradition", () => {
    const r = toCanonical({
      book: "Genesis",
      bookNum: 1,
      chapter: 1,
      verseStart: 1,
      fromTradition: "nwt",
      toTradition: "nwt",
    });
    expect(r.isDiscrepant).toBe(false);
    expect(r.coord.chapter).toBe(1);
  });

  it("Joel 2:28-32 NWT → Joel 3:1-5 BHS", () => {
    const r = toCanonical({
      book: "Joel",
      bookNum: 29,
      chapter: 2,
      verseStart: 28,
      verseEnd: 32,
      fromTradition: "nwt",
      toTradition: "masoretic",
    });
    expect(r.isDiscrepant).toBe(true);
    expect(r.coord.chapter).toBe(3);
    expect(r.coord.verseStart).toBe(1);
    expect(r.coord.verseEnd).toBe(5);
  });

  it("round-trip preserves Joel 2:28", () => {
    const fwd = toCanonical({
      book: "Joel",
      bookNum: 29,
      chapter: 2,
      verseStart: 28,
      verseEnd: 32,
      fromTradition: "nwt",
      toTradition: "masoretic",
    });
    const back = toCanonical({
      book: fwd.refBook,
      bookNum: fwd.refBookNum,
      chapter: fwd.coord.chapter,
      verseStart: fwd.coord.verseStart,
      verseEnd: fwd.coord.verseEnd ?? undefined,
      fromTradition: "masoretic",
      toTradition: "nwt",
    });
    expect(back.coord.chapter).toBe(2);
    expect(back.coord.verseStart).toBe(28);
    expect(back.coord.verseEnd).toBe(32);
  });

  it("Malachi 4 NWT → Malachi 3:19 BHS", () => {
    const r = toCanonical({
      book: "Malachi",
      bookNum: 39,
      chapter: 4,
      verseStart: 1,
      verseEnd: 6,
      fromTradition: "nwt",
      toTradition: "masoretic",
    });
    expect(r.coord.chapter).toBe(3);
    expect(r.coord.verseStart).toBe(19);
    expect(r.coord.verseEnd).toBe(24);
  });

  it("throws on unknown tradition", () => {
    expect(() =>
      toCanonical({
        book: "Genesis",
        bookNum: 1,
        chapter: 1,
        verseStart: 1,
        // @ts-expect-error testing runtime guard
        toTradition: "aramaic",
      }),
    ).toThrow(/Unknown toTradition/);
  });
});

describe("explain", () => {
  it("returns null on identity mapping", () => {
    expect(
      explain({
        book: "Genesis",
        bookNum: 1,
        chapter: 1,
        verseStart: 1,
        fromTradition: "nwt",
        toTradition: "nwt",
      }),
    ).toBeNull();
  });

  it("returns trilingual rationale for Joel 2:28 → Spanish", () => {
    const out = explain({
      book: "Joel",
      bookNum: 29,
      chapter: 2,
      verseStart: 28,
      fromTradition: "nwt",
      toTradition: "masoretic",
      language: "es",
    });
    expect(out).toBeTruthy();
    expect(out).toMatch(/Joel/);
    expect(out).toMatch(/masorético/);
  });
});
