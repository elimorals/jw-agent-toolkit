/**
 * F56.5 — tests for BibleRef.fromWolUrl() and langFromWolPath().
 *
 * These two helpers are the inverse of `wolUrl()` and let consumers
 * (the WOL extension, and a hypothetical future Capacitor app) parse
 * canonical wol.jw.org URLs back into structured refs without
 * reinventing the regex per project.
 */

import { describe, expect, it } from "vitest";

import { BibleRef, langFromWolPath } from "../src/index.js";

describe("BibleRef.fromWolUrl", () => {
  it("parses a chapter-only Spanish URL", () => {
    const ref = BibleRef.fromWolUrl(
      "https://wol.jw.org/es/wol/b/r4/lp-s/nwtsty/43/3",
    );
    expect(ref).not.toBeNull();
    expect(ref?.bookNum).toBe(43);
    expect(ref?.chapter).toBe(3);
    expect(ref?.bookCanonical).toBe("John");
    expect(ref?.detectedLanguage).toBe("es");
    expect(ref?.verseStart).toBeNull();
  });

  it("parses an English chapter URL", () => {
    const ref = BibleRef.fromWolUrl(
      "https://wol.jw.org/en/wol/b/r1/lp-e/nwtsty/1/1",
    );
    expect(ref?.bookNum).toBe(1);
    expect(ref?.chapter).toBe(1);
    expect(ref?.detectedLanguage).toBe("en");
  });

  it("parses a Portuguese chapter URL using legacy /t/ segment", () => {
    const ref = BibleRef.fromWolUrl(
      "https://wol.jw.org/t/wol/b/r5/lp-t/nwtsty/19/23",
    );
    expect(ref?.bookNum).toBe(19);
    expect(ref?.chapter).toBe(23);
    expect(ref?.detectedLanguage).toBe("pt");
  });

  it("extracts verseStart from the #v=BB:CC:VV anchor", () => {
    const ref = BibleRef.fromWolUrl(
      "https://wol.jw.org/es/wol/b/r4/lp-s/nwtsty/43/3#study=discover&v=43:3:16",
    );
    expect(ref?.verseStart).toBe(16);
    expect(ref?.verseEnd).toBeNull();
  });

  it("round-trips wolUrl() → fromWolUrl()", () => {
    const original = new BibleRef({
      bookNum: 43,
      bookCanonical: "John",
      chapter: 3,
      verseStart: 16,
      verseEnd: null,
      detectedLanguage: "es",
      rawMatch: "Juan 3:16",
    });
    const url = original.wolUrl("es");
    const parsed = BibleRef.fromWolUrl(url);
    expect(parsed?.bookNum).toBe(original.bookNum);
    expect(parsed?.chapter).toBe(original.chapter);
    expect(parsed?.verseStart).toBe(original.verseStart);
    expect(parsed?.detectedLanguage).toBe(original.detectedLanguage);
  });

  it("returns null for non-WOL hosts", () => {
    expect(BibleRef.fromWolUrl("https://example.com/wol/b/r1/lp-e/nwtsty/43/3")).toBeNull();
    expect(BibleRef.fromWolUrl("https://jw.org/finder?wtlocale=S")).toBeNull();
  });

  it("returns null for malformed URLs", () => {
    expect(BibleRef.fromWolUrl("not a url at all")).toBeNull();
    expect(BibleRef.fromWolUrl("")).toBeNull();
  });

  it("returns null for out-of-range book numbers", () => {
    expect(
      BibleRef.fromWolUrl("https://wol.jw.org/en/wol/b/r1/lp-e/nwtsty/67/1"),
    ).toBeNull();
    expect(
      BibleRef.fromWolUrl("https://wol.jw.org/en/wol/b/r1/lp-e/nwtsty/0/1"),
    ).toBeNull();
  });

  it("ignores broken anchor verses", () => {
    const ref = BibleRef.fromWolUrl(
      "https://wol.jw.org/en/wol/b/r1/lp-e/nwtsty/43/3#v=garbage",
    );
    expect(ref?.verseStart).toBeNull();
  });
});

describe("langFromWolPath", () => {
  it("recognizes ISO-639-1 prefixes", () => {
    expect(langFromWolPath("en")).toBe("en");
    expect(langFromWolPath("es")).toBe("es");
    expect(langFromWolPath("pt")).toBe("pt");
    expect(langFromWolPath("pt-BR")).toBe("pt");
  });

  it("recognizes WOL legacy single-letter segments", () => {
    expect(langFromWolPath("e")).toBe("en");
    expect(langFromWolPath("s")).toBe("es");
    expect(langFromWolPath("t")).toBe("pt");
  });

  it("extracts language from a full URL", () => {
    expect(langFromWolPath("https://wol.jw.org/es/wol/b/r4/lp-s/nwtsty/43/3")).toBe("es");
    expect(langFromWolPath("https://wol.jw.org/t/wol/b/r5/lp-t/nwt/1/1")).toBe("pt");
  });

  it("extracts language from a path-only string", () => {
    expect(langFromWolPath("/es/wol/b/r4/lp-s/nwtsty/43/3")).toBe("es");
  });

  it("returns null for unsupported languages", () => {
    expect(langFromWolPath("fr")).toBeNull();
    expect(langFromWolPath("de")).toBeNull();
    expect(langFromWolPath("zh-CN")).toBeNull();
  });

  it("returns null for empty input", () => {
    expect(langFromWolPath("")).toBeNull();
  });
});
