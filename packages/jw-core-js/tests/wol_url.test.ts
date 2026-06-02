import { describe, expect, it } from "vitest";

import { BibleRef, parseReference } from "../src/index.js";

describe("BibleRef.wolUrl", () => {
  it("emits the English NWTsty URL for John 3:16", () => {
    const ref = parseReference("John 3:16");
    expect(ref).not.toBeNull();
    const url = (ref as BibleRef).wolUrl("en");
    expect(url).toBe(
      "https://wol.jw.org/en/wol/b/r1/lp-e/nwtsty/43/3#study=discover&v=43:3:16",
    );
  });

  it("emits the Spanish NWT URL for Juan 3:16", () => {
    const ref = parseReference("Juan 3:16");
    const url = (ref as BibleRef).wolUrl("es");
    expect(url).toBe(
      "https://wol.jw.org/es/wol/b/r4/lp-s/nwt/43/3#study=discover&v=43:3:16",
    );
  });

  it("omits the verse anchor when only a chapter is parsed", () => {
    const ref = parseReference("Mateo 5");
    const url = (ref as BibleRef).wolUrl("es");
    expect(url).toBe("https://wol.jw.org/es/wol/b/r4/lp-s/nwt/40/5");
  });

  it("respects an explicit `pub` override", () => {
    const ref = parseReference("Juan 3:16");
    const url = (ref as BibleRef).wolUrl("es", "rbi8");
    expect(url).toContain("/rbi8/43/3");
  });
});

describe("BibleRef.display + JSON shape", () => {
  it("display() returns canonical English form", () => {
    const ref = parseReference("Juan 3:16-18");
    expect(ref?.display()).toBe("John 3:16-18");
  });

  it("toJSON() exposes camelCase fields suitable for IPC", () => {
    const ref = parseReference("Heb 11:1");
    const json = ref?.toJSON();
    expect(json).toMatchObject({
      bookNum: 58,
      bookCanonical: "Hebrews",
      chapter: 11,
      verseStart: 1,
    });
  });
});
