import { describe, expect, it } from "vitest";

import { createTranslator, detectLanguage } from "../../src/i18n";

describe("i18n", () => {
  it("returns es translation when language is es", () => {
    const t = createTranslator("es");
    expect(t("action.explain")).toMatch(/explica/i);
  });

  it("falls back to en when language is unknown", () => {
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const t = createTranslator("xx" as any);
    expect(t("action.explain")).toMatch(/explain/i);
  });

  it("returns the key itself when message is missing", () => {
    const t = createTranslator("en");
    expect(t("missing.thing.xyz")).toBe("missing.thing.xyz");
  });

  it("interpolates {param} placeholders", () => {
    const t = createTranslator("en");
    expect(t("toast.saved", { path: "/v/x.md" })).toBe("Saved to /v/x.md");
  });

  it("detectLanguage maps wol path prefix", () => {
    expect(detectLanguage("https://wol.jw.org/es/wol/h/r4")).toBe("es");
    expect(detectLanguage("https://wol.jw.org/en/wol/h/r1")).toBe("en");
    expect(detectLanguage("https://wol.jw.org/t/wol/h/r1")).toBe("pt");
  });

  it("detectLanguage falls back to en on unknown prefix", () => {
    expect(detectLanguage("https://wol.jw.org/xx/wol/h/r1")).toBe("en");
  });
});
