import { beforeEach, describe, expect, it, vi } from "vitest";

import { injectButtonsForVerses } from "../../src/dom/button_injector";
import { detectVerses } from "../../src/dom/verse_detector";

const HTML = `
  <p>
    <span class="verse" data-verse="1"><sup class="verseNum">1</sup>uno</span>
    <span class="verse" data-verse="2"><sup class="verseNum">2</sup>dos</span>
  </p>
`;

describe("injectButtonsForVerses", () => {
  beforeEach(() => {
    document.body.innerHTML = HTML;
  });

  it("appends exactly one action container per verse", () => {
    const verses = detectVerses(document, { book: "Juan", chapter: 3 });
    injectButtonsForVerses(verses, {
      onExplain: vi.fn(),
      onCrossRefs: vi.fn(),
      onSaveVault: vi.fn(),
      t: (k) => k,
    });
    expect(document.querySelectorAll(".jw-ext-verse-actions")).toHaveLength(2);
  });

  it("is idempotent: a second call does not duplicate buttons", () => {
    const verses = detectVerses(document, { book: "Juan", chapter: 3 });
    const handlers = {
      onExplain: vi.fn(),
      onCrossRefs: vi.fn(),
      onSaveVault: vi.fn(),
      t: (k: string) => k,
    };
    injectButtonsForVerses(verses, handlers);
    injectButtonsForVerses(verses, handlers);
    expect(document.querySelectorAll(".jw-ext-verse-actions")).toHaveLength(2);
  });

  it("wires the click on explain to the handler", () => {
    const verses = detectVerses(document, { book: "Juan", chapter: 3 });
    const onExplain = vi.fn();
    injectButtonsForVerses(verses, {
      onExplain,
      onCrossRefs: vi.fn(),
      onSaveVault: vi.fn(),
      t: (k) => k,
    });
    const btn = document.querySelector<HTMLButtonElement>(
      "[data-verse='1'] .jw-ext-btn-explain",
    );
    btn?.click();
    expect(onExplain).toHaveBeenCalledOnce();
    expect(onExplain.mock.calls[0]![0].reference).toBe("Juan 3:1");
  });

  it("uses translator for aria-labels", () => {
    const verses = detectVerses(document, { book: "Juan", chapter: 3 });
    const t = vi.fn((k: string) => `TR(${k})`);
    injectButtonsForVerses(verses, {
      onExplain: vi.fn(),
      onCrossRefs: vi.fn(),
      onSaveVault: vi.fn(),
      t,
    });
    const btn = document.querySelector<HTMLButtonElement>(".jw-ext-btn-explain");
    expect(btn?.getAttribute("aria-label")).toBe("TR(action.explain)");
  });

  it("does not modify the verse <span> content", () => {
    const original = document.querySelectorAll("span.verse")[0]!.textContent;
    const verses = detectVerses(document, { book: "Juan", chapter: 3 });
    injectButtonsForVerses(verses, {
      onExplain: vi.fn(),
      onCrossRefs: vi.fn(),
      onSaveVault: vi.fn(),
      t: (k) => k,
    });
    expect(document.querySelectorAll("span.verse")[0]!.textContent).toBe(
      original,
    );
  });
});
