import { beforeEach, describe, expect, it, vi } from "vitest";

import { run } from "../../src/content_script";

const HTML = `
  <p>
    <span class="verse" data-verse="1"><sup class="verseNum">1</sup>uno</span>
    <span class="verse" data-verse="2"><sup class="verseNum">2</sup>dos</span>
  </p>
`;

interface WindowWithTestUrl {
  __JW_TEST_URL__?: string;
}

describe("content_script.run", () => {
  beforeEach(() => {
    document.body.innerHTML = HTML;
    // happy-dom URL handling — override via the same global the bootstrap
    // checks (avoids touching window.location which is read-only in jsdom).
    (window as unknown as WindowWithTestUrl).__JW_TEST_URL__ =
      "https://wol.jw.org/es/wol/b/r4/lp-s/nwt/E/2024/43/3";
  });

  it("injects buttons when chapter context can be derived", () => {
    run({
      onExplain: vi.fn(),
      onCrossRefs: vi.fn(),
      onSaveVault: vi.fn(),
    });
    expect(document.querySelectorAll(".jw-ext-verse-actions")).toHaveLength(2);
  });

  it("is a no-op on a non-bible URL", () => {
    (window as unknown as WindowWithTestUrl).__JW_TEST_URL__ =
      "https://wol.jw.org/es/wol/h/r4/lp-s";
    run({
      onExplain: vi.fn(),
      onCrossRefs: vi.fn(),
      onSaveVault: vi.fn(),
    });
    expect(document.querySelectorAll(".jw-ext-verse-actions")).toHaveLength(0);
  });
});
