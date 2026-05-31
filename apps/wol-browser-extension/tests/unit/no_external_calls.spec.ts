import { readFileSync, readdirSync, statSync } from "node:fs";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";

import { describe, expect, it } from "vitest";

// happy-dom rewrites ``import.meta.url`` to a relative URL whose pathname
// resolves to ``/src`` — bypass it by using ``fileURLToPath`` only when the
// URL is a real file:// one; otherwise fall back to ``process.cwd()``.
const HERE = (() => {
  try {
    return dirname(fileURLToPath(import.meta.url));
  } catch {
    return process.cwd();
  }
})();
const SRC = resolve(HERE, "..", "..", "src");
const ALLOWED_HOST_LITERAL = "http://localhost:8765";

function walk(dir: string, acc: string[] = []): string[] {
  for (const e of readdirSync(dir)) {
    const p = join(dir, e);
    const s = statSync(p);
    if (s.isDirectory()) walk(p, acc);
    else if (/\.(ts|tsx|js|mjs)$/.test(e)) acc.push(p);
  }
  return acc;
}

describe("static guard: no external URLs in src/", () => {
  it("never embeds an http(s) URL other than the API_BASE literal", () => {
    const files = walk(SRC);
    const violations: { file: string; line: number; text: string }[] = [];
    const re = /https?:\/\/[^\s"'`<>]+/g;
    for (const f of files) {
      const text = readFileSync(f, "utf-8");
      const lines = text.split("\n");
      lines.forEach((ln, i) => {
        // Strip single-line comments before scanning so commentary URLs
        // (e.g. JSDoc example links) don't count.
        const code = ln.replace(/\/\/.*$/, "");
        for (const match of code.matchAll(re)) {
          const url = match[0];
          if (url.startsWith(ALLOWED_HOST_LITERAL)) continue;
          // The verse_detector and content_script need literal wol.jw.org
          // hostname checks / pattern matchers; allow them explicitly.
          if (
            url.startsWith("https://wol.jw.org/") &&
            (f.includes("verse_detector") || f.includes("content_script"))
          ) {
            continue;
          }
          violations.push({ file: f, line: i + 1, text: ln.trim() });
        }
      });
    }
    expect(violations, JSON.stringify(violations, null, 2)).toEqual([]);
  });
});
