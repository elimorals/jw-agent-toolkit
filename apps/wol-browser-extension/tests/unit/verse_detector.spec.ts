import { beforeEach, describe, expect, it } from "vitest";

import {
  buildReferenceFromUrl,
  detectVerses,
} from "../../src/dom/verse_detector";

const SAMPLE = `
  <h1>Juan 3</h1>
  <p>
    <span id="v43003001" class="verse" data-verse="1"><sup class="verseNum">1</sup>Había un hombre de los fariseos.</span>
    <span id="v43003002" class="verse" data-verse="2"><sup class="verseNum">2</sup>Este vino a Jesús de noche.</span>
    <span id="v43003016" class="verse" data-verse="16"><sup class="verseNum">16</sup>Porque Dios amó tanto al mundo.</span>
  </p>
`;

describe("detectVerses", () => {
  beforeEach(() => {
    document.body.innerHTML = SAMPLE;
  });

  it("finds every <span class='verse'> on the page", () => {
    const verses = detectVerses(document, { book: "Juan", chapter: 3 });
    expect(verses).toHaveLength(3);
    expect(verses.map((v) => v.verseNum)).toEqual([1, 2, 16]);
  });

  it("builds human references with the chapter context", () => {
    const verses = detectVerses(document, { book: "Juan", chapter: 3 });
    expect(verses[2]!.reference).toBe("Juan 3:16");
  });

  it("skips spans without a data-verse attribute", () => {
    document.body.innerHTML = `
      <span class="verse">no number</span>
      <span class="verse" data-verse="5">five</span>
    `;
    const verses = detectVerses(document, { book: "Juan", chapter: 3 });
    expect(verses).toHaveLength(1);
    expect(verses[0]!.verseNum).toBe(5);
  });

  it("returns empty array when chapter context cannot be derived", () => {
    document.body.innerHTML = `<span class="verse" data-verse="1">x</span>`;
    const verses = detectVerses(document, null);
    expect(verses).toEqual([]);
  });
});

describe("buildReferenceFromUrl", () => {
  it("parses a canonical wol path", () => {
    const ctx = buildReferenceFromUrl(
      "https://wol.jw.org/es/wol/b/r4/lp-s/nwt/E/2024/43/3",
    );
    expect(ctx).toEqual({ book: "Juan", chapter: 3 });
  });

  it("returns null for a non-bible page", () => {
    expect(
      buildReferenceFromUrl("https://wol.jw.org/es/wol/h/r4/lp-s"),
    ).toBeNull();
  });
});
