# Fase 48 — `wol-browser-extension` Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship `apps/wol-browser-extension/`, a Chrome/Edge/Firefox extension (Manifest v3) that injects inline action buttons (📖 Explain, 🔗 Cross-refs, 📝 Save to Obsidian) into every `<span class="verse">` on `wol.jw.org`, calling a strictly-local FastAPI backend (`http://localhost:8765`). The extension never makes a request to any origin other than `localhost:8765` and the page itself, enforced at three levels (manifest, lint, runtime test).

**Architecture:** New monorepo workspace member `apps/wol-browser-extension/` (TypeScript + Vite + `@crxjs/vite-plugin`). Content script detects verses, popup UI persists settings (vault path, language) in `chrome.storage.local`, background service worker handles health-check and request dispatch. Backend changes are surgical: tighten CORS from `allow_origins=["*"]` to an explicit regex whitelist, add `POST /api/v1/cross_references`, add `POST /api/v1/vault/append` with **vault path validation** (must contain `.obsidian/` to defend against the `~/.ssh` exfiltration risk). Tests use Playwright + a mocked WOL fixture HTML and a mocked backend on `127.0.0.1:8765`.

**Tech Stack:** TypeScript 5.5 · Vite 5 · `@crxjs/vite-plugin` 2.x · Playwright 1.46 · Vitest 2.x · pnpm 9 · ESLint 9 + `eslint-plugin-no-restricted-syntax` · Python (FastAPI, pydantic, pytest, starlette CORS).

**Spec:** [`docs/superpowers/specs/2026-05-31-fase-48-wol-browser-ext-design.md`](../specs/2026-05-31-fase-48-wol-browser-ext-design.md).

---

## File map

Creates:
- `apps/wol-browser-extension/package.json`
- `apps/wol-browser-extension/pnpm-workspace.yaml` (or join existing one at repo root)
- `apps/wol-browser-extension/tsconfig.json`
- `apps/wol-browser-extension/vite.config.ts`
- `apps/wol-browser-extension/manifest.json`
- `apps/wol-browser-extension/.eslintrc.cjs`
- `apps/wol-browser-extension/.gitignore`
- `apps/wol-browser-extension/README.md`
- `apps/wol-browser-extension/src/types.ts`
- `apps/wol-browser-extension/src/config.ts`
- `apps/wol-browser-extension/src/api.ts`
- `apps/wol-browser-extension/src/background.ts`
- `apps/wol-browser-extension/src/content_script.ts`
- `apps/wol-browser-extension/src/dom/verse_detector.ts`
- `apps/wol-browser-extension/src/dom/button_injector.ts`
- `apps/wol-browser-extension/src/dom/tooltip.ts`
- `apps/wol-browser-extension/src/dom/styles.css`
- `apps/wol-browser-extension/src/i18n/index.ts`
- `apps/wol-browser-extension/src/i18n/en.json`
- `apps/wol-browser-extension/src/i18n/es.json`
- `apps/wol-browser-extension/src/i18n/pt.json`
- `apps/wol-browser-extension/src/popup/popup.html`
- `apps/wol-browser-extension/src/popup/popup.ts`
- `apps/wol-browser-extension/src/popup/popup.css`
- `apps/wol-browser-extension/icons/16.png`
- `apps/wol-browser-extension/icons/48.png`
- `apps/wol-browser-extension/icons/128.png`
- `apps/wol-browser-extension/tests/unit/api.spec.ts`
- `apps/wol-browser-extension/tests/unit/verse_detector.spec.ts`
- `apps/wol-browser-extension/tests/unit/button_injector.spec.ts`
- `apps/wol-browser-extension/tests/unit/no_external_calls.spec.ts`
- `apps/wol-browser-extension/tests/unit/i18n.spec.ts`
- `apps/wol-browser-extension/tests/playwright/playwright.config.ts`
- `apps/wol-browser-extension/tests/playwright/mock_backend.ts`
- `apps/wol-browser-extension/tests/playwright/fixture_pages/john_3_es.html`
- `apps/wol-browser-extension/tests/playwright/fixture_pages/john_3_en.html`
- `apps/wol-browser-extension/tests/playwright/extension.spec.ts`
- `apps/wol-browser-extension/tests/playwright/privacy.spec.ts`
- `apps/wol-browser-extension/scripts/package.mjs`
- `.github/workflows/wol-extension.yml`
- `packages/jw-mcp/tests/test_cors_origins.py`
- `packages/jw-mcp/tests/test_cross_references_endpoint.py`
- `packages/jw-mcp/tests/test_vault_append_endpoint.py`

Modifies:
- `pnpm-workspace.yaml` (repo root) — add `apps/wol-browser-extension`.
- `packages/jw-mcp/src/jw_mcp/rest_api.py` — tighten CORS, add 2 endpoints + vault validation.
- `packages/jw-mcp/pyproject.toml` — no new dep, but pinning `starlette` reused.
- `docs/VISION_AUDIT.md` — add Fase 48 row.
- `docs/ROADMAP.md` — add Fase 48 section.
- `docs/guias/README.md` — link the new guide.
- `docs/guias/wol-browser-ext.md` — install/usage walk-through.

---

### Task 1: Scaffold `apps/wol-browser-extension/` workspace + manifest

**Files:**
- Create: `apps/wol-browser-extension/package.json`
- Create: `apps/wol-browser-extension/tsconfig.json`
- Create: `apps/wol-browser-extension/vite.config.ts`
- Create: `apps/wol-browser-extension/manifest.json`
- Create: `apps/wol-browser-extension/.gitignore`
- Create: `apps/wol-browser-extension/README.md`
- Modify: `pnpm-workspace.yaml`

- [x] **Step 1: Write the failing test (scaffold sanity)**

```typescript
// apps/wol-browser-extension/tests/unit/manifest.spec.ts
import { describe, it, expect } from "vitest";
import manifest from "../../manifest.json";

describe("manifest v3 contract", () => {
  it("declares manifest_version 3", () => {
    expect(manifest.manifest_version).toBe(3);
  });

  it("only allows localhost:8765 in host_permissions", () => {
    expect(manifest.host_permissions).toEqual(["http://localhost:8765/*"]);
  });

  it("content_scripts target wol.jw.org only", () => {
    expect(manifest.content_scripts).toHaveLength(1);
    expect(manifest.content_scripts[0].matches).toEqual(["https://wol.jw.org/*"]);
  });

  it("permissions list is minimal (storage only)", () => {
    expect(manifest.permissions).toEqual(["storage"]);
    expect(manifest.permissions).not.toContain("tabs");
    expect(manifest.permissions).not.toContain("webRequest");
    expect(manifest.permissions).not.toContain("cookies");
  });

  it("declares a Firefox gecko id for self-distribution AMO", () => {
    expect(manifest.browser_specific_settings?.gecko?.id).toBe(
      "jw-agent-toolkit@cipre.dev"
    );
  });
});
```

- [x] **Step 2: Run test to verify it fails**

Run: `cd apps/wol-browser-extension && pnpm vitest run tests/unit/manifest.spec.ts`
Expected: FAIL — `manifest.json` does not exist.

- [x] **Step 3: Create the manifest, tsconfig, vite config and package.json**

```json
// apps/wol-browser-extension/package.json
{
  "name": "@jw-agent-toolkit/wol-browser-extension",
  "version": "0.1.0",
  "description": "Chrome/Edge/Firefox extension that injects inline actions for wol.jw.org. 100% local.",
  "private": true,
  "type": "module",
  "scripts": {
    "dev": "vite",
    "build": "vite build",
    "package": "pnpm build && node scripts/package.mjs",
    "test": "vitest run",
    "test:e2e": "playwright test --config tests/playwright/playwright.config.ts",
    "test:privacy": "playwright test --config tests/playwright/playwright.config.ts privacy.spec.ts",
    "lint": "eslint 'src/**/*.{ts,tsx}'",
    "typecheck": "tsc --noEmit"
  },
  "dependencies": {},
  "devDependencies": {
    "@crxjs/vite-plugin": "^2.0.0-beta.27",
    "@playwright/test": "^1.46.0",
    "@types/chrome": "^0.0.268",
    "@types/node": "^22.0.0",
    "@typescript-eslint/eslint-plugin": "^8.5.0",
    "@typescript-eslint/parser": "^8.5.0",
    "eslint": "^9.10.0",
    "eslint-plugin-no-restricted-syntax": "^0.0.1",
    "happy-dom": "^15.0.0",
    "typescript": "^5.5.4",
    "vite": "^5.4.0",
    "vitest": "^2.0.5"
  }
}
```

```json
// apps/wol-browser-extension/tsconfig.json
{
  "compilerOptions": {
    "target": "ES2022",
    "module": "ESNext",
    "moduleResolution": "Bundler",
    "lib": ["ES2022", "DOM", "DOM.Iterable"],
    "strict": true,
    "noImplicitAny": true,
    "strictNullChecks": true,
    "noUncheckedIndexedAccess": true,
    "esModuleInterop": true,
    "resolveJsonModule": true,
    "isolatedModules": true,
    "skipLibCheck": true,
    "types": ["chrome", "node"]
  },
  "include": ["src/**/*", "tests/**/*", "manifest.json"]
}
```

```typescript
// apps/wol-browser-extension/vite.config.ts
import { defineConfig } from "vite";
import { crx } from "@crxjs/vite-plugin";
import manifest from "./manifest.json" assert { type: "json" };

export default defineConfig({
  plugins: [crx({ manifest })],
  build: {
    outDir: "dist",
    emptyOutDir: true,
    sourcemap: false,
    rollupOptions: {
      output: {
        chunkFileNames: "assets/chunk-[hash].js",
      },
    },
  },
  // Vitest config
  test: {
    environment: "happy-dom",
    globals: false,
    include: ["tests/unit/**/*.spec.ts"],
  },
});
```

```json
// apps/wol-browser-extension/manifest.json
{
  "manifest_version": 3,
  "name": "JW Agent Toolkit — WOL Companion",
  "short_name": "JW Toolkit WOL",
  "version": "0.1.0",
  "description": "Inline explanations, cross-references, and Obsidian export for wol.jw.org. 100% local.",
  "default_locale": "en",
  "icons": {
    "16": "icons/16.png",
    "48": "icons/48.png",
    "128": "icons/128.png"
  },
  "action": {
    "default_popup": "src/popup/popup.html",
    "default_icon": "icons/48.png",
    "default_title": "JW Toolkit WOL"
  },
  "background": {
    "service_worker": "src/background.ts",
    "type": "module"
  },
  "content_scripts": [
    {
      "matches": ["https://wol.jw.org/*"],
      "js": ["src/content_script.ts"],
      "css": ["src/dom/styles.css"],
      "run_at": "document_idle"
    }
  ],
  "host_permissions": ["http://localhost:8765/*"],
  "permissions": ["storage"],
  "browser_specific_settings": {
    "gecko": {
      "id": "jw-agent-toolkit@cipre.dev",
      "strict_min_version": "121.0"
    }
  }
}
```

```gitignore
# apps/wol-browser-extension/.gitignore
node_modules/
dist/
dist-zip/
.vite/
playwright-report/
test-results/
*.log
```

Edit repo root `pnpm-workspace.yaml`:

```yaml
packages:
  - "packages/*"
  - "apps/*"          # add this if not present
```

- [x] **Step 4: Run test to verify it passes**

```bash
cd apps/wol-browser-extension
pnpm install
pnpm vitest run tests/unit/manifest.spec.ts
```
Expected: 5 passed.

- [x] **Step 5: Commit**

```bash
git add apps/wol-browser-extension pnpm-workspace.yaml
git commit -m "feat(wol-ext): scaffold workspace + manifest v3 with localhost-only host_permissions"
```

---

### Task 2: API client (`src/api.ts`) with hard URL allow-list

**Files:**
- Create: `apps/wol-browser-extension/src/config.ts`
- Create: `apps/wol-browser-extension/src/types.ts`
- Create: `apps/wol-browser-extension/src/api.ts`
- Create: `apps/wol-browser-extension/tests/unit/api.spec.ts`

- [x] **Step 1: Write the failing test**

```typescript
// apps/wol-browser-extension/tests/unit/api.spec.ts
import { describe, it, expect, beforeEach, vi } from "vitest";
import { JwApiClient, ApiError } from "../../src/api";

describe("JwApiClient", () => {
  let fetchMock: ReturnType<typeof vi.fn>;

  beforeEach(() => {
    fetchMock = vi.fn();
    globalThis.fetch = fetchMock as unknown as typeof fetch;
  });

  it("only ever calls http://localhost:8765", async () => {
    fetchMock.mockResolvedValueOnce(
      new Response(JSON.stringify({ status: "ok" }), { status: 200 })
    );
    const client = new JwApiClient();
    await client.health();
    expect(fetchMock).toHaveBeenCalledOnce();
    const url = fetchMock.mock.calls[0]![0] as string;
    expect(url.startsWith("http://localhost:8765/")).toBe(true);
  });

  it("refuses to construct a request to a non-localhost URL", async () => {
    const client = new JwApiClient();
    await expect(
      // @ts-expect-error: testing private guard
      client["request"]("https://wol.jw.org/evil", "GET")
    ).rejects.toThrow(/non-localhost/);
  });

  it("verse_markdown POSTs reference body and returns markdown", async () => {
    fetchMock.mockResolvedValueOnce(
      new Response(
        JSON.stringify({
          markdown: "> Juan 3:16 ...",
          reference: "Juan 3:16",
          language: "es",
          source_url: "https://wol.jw.org/x",
        }),
        { status: 200 }
      )
    );
    const client = new JwApiClient();
    const out = await client.verseMarkdown({
      reference: "Juan 3:16",
      language: "es",
      template: "callout",
    });
    expect(out.markdown).toContain("Juan 3:16");
    const [, init] = fetchMock.mock.calls[0]!;
    expect((init as RequestInit).method).toBe("POST");
    expect(JSON.parse((init as RequestInit).body as string)).toEqual({
      reference: "Juan 3:16",
      language: "es",
      template: "callout",
    });
  });

  it("throws ApiError on non-2xx", async () => {
    fetchMock.mockResolvedValueOnce(
      new Response(JSON.stringify({ detail: "bad" }), { status: 400 })
    );
    const client = new JwApiClient();
    await expect(client.health()).rejects.toBeInstanceOf(ApiError);
  });

  it("returns null on network failure (does not surface URL)", async () => {
    fetchMock.mockRejectedValueOnce(new TypeError("Failed to fetch"));
    const client = new JwApiClient();
    const ok = await client.healthOrNull();
    expect(ok).toBe(null);
  });

  it("crossRefs invokes /api/v1/cross_references", async () => {
    fetchMock.mockResolvedValueOnce(
      new Response(JSON.stringify({ refs: [{ verse: "John 1:1", url: "x" }] }), {
        status: 200,
      })
    );
    const client = new JwApiClient();
    const out = await client.crossRefs({ reference: "John 3:16", language: "en" });
    expect(out.refs).toHaveLength(1);
    expect(fetchMock.mock.calls[0]![0]).toBe(
      "http://localhost:8765/api/v1/cross_references"
    );
  });

  it("vaultAppend invokes /api/v1/vault/append", async () => {
    fetchMock.mockResolvedValueOnce(
      new Response(JSON.stringify({ ok: true, path: "/v/Verses/x.md" }), {
        status: 200,
      })
    );
    const client = new JwApiClient();
    const out = await client.vaultAppend({
      reference: "John 3:16",
      vault_path: "/Users/x/vault",
      template: "callout",
      language: "en",
    });
    expect(out.ok).toBe(true);
    expect(fetchMock.mock.calls[0]![0]).toBe(
      "http://localhost:8765/api/v1/vault/append"
    );
  });
});
```

- [x] **Step 2: Run test to verify it fails**

Run: `pnpm vitest run tests/unit/api.spec.ts`
Expected: FAIL — `JwApiClient` missing.

- [x] **Step 3: Implement config, types and api**

```typescript
// apps/wol-browser-extension/src/config.ts
/**
 * Hard configuration. The base URL is a literal so eslint can statically
 * verify no other URL is reachable from a fetch() call site.
 */
export const API_BASE = "http://localhost:8765" as const;
export const HEALTH_TIMEOUT_MS = 2_000;
export const REQUEST_TIMEOUT_MS = 15_000;
```

```typescript
// apps/wol-browser-extension/src/types.ts
export type Language = "en" | "es" | "pt";
export type Template = "plain" | "link" | "blockquote" | "callout" | "callout-collapsed";

export interface VerseMarkdownRequest {
  reference: string;
  language: Language;
  template: Template;
  length?: "short" | "medium" | "long";
  include_text?: boolean;
}

export interface VerseMarkdownResponse {
  markdown: string;
  reference: string;
  language: string;
  source_url: string;
  error?: string;
}

export interface CrossRefRequest {
  reference: string;
  language: Language;
}

export interface CrossRefHit {
  verse: string;
  url: string;
  excerpt?: string;
}

export interface CrossRefResponse {
  refs: CrossRefHit[];
}

export interface VaultAppendRequest {
  reference: string;
  vault_path: string;
  template: Template;
  language: Language;
  subdir?: string;
}

export interface VaultAppendResponse {
  ok: boolean;
  path: string;
  error?: string;
}

export interface VerseTarget {
  /** Numeric verse number as printed on the page. */
  verseNum: number;
  /** Human reference such as `Juan 3:16`. */
  reference: string;
  /** The DOM node containing the verse text. */
  node: HTMLElement;
}
```

```typescript
// apps/wol-browser-extension/src/api.ts
import { API_BASE, HEALTH_TIMEOUT_MS, REQUEST_TIMEOUT_MS } from "./config";
import type {
  CrossRefRequest,
  CrossRefResponse,
  VaultAppendRequest,
  VaultAppendResponse,
  VerseMarkdownRequest,
  VerseMarkdownResponse,
} from "./types";

export class ApiError extends Error {
  constructor(
    public readonly status: number,
    public readonly bodyExcerpt: string
  ) {
    super(`API ${status}: ${bodyExcerpt.slice(0, 200)}`);
  }
}

/**
 * Thin wrapper around fetch. Refuses to call any URL not starting with
 * API_BASE — defense-in-depth on top of manifest host_permissions.
 */
export class JwApiClient {
  private readonly base: string;

  constructor(base: string = API_BASE) {
    if (base !== API_BASE) {
      throw new Error(
        `JwApiClient refuses non-default base ${base!r} (only ${API_BASE} allowed)`
      );
    }
    this.base = base;
  }

  private assertLocal(url: string): void {
    if (!url.startsWith(`${API_BASE}/`)) {
      throw new Error(`refuses non-localhost URL: ${url}`);
    }
  }

  private async request<T>(
    url: string,
    method: "GET" | "POST",
    body?: unknown,
    timeoutMs: number = REQUEST_TIMEOUT_MS
  ): Promise<T> {
    this.assertLocal(url);
    const ctrl = new AbortController();
    const timer = setTimeout(() => ctrl.abort(), timeoutMs);
    try {
      const init: RequestInit = {
        method,
        headers: body ? { "Content-Type": "application/json" } : {},
        signal: ctrl.signal,
      };
      if (body) {
        init.body = JSON.stringify(body);
      }
      const r = await fetch(url, init);
      if (!r.ok) {
        const text = await r.text();
        throw new ApiError(r.status, text);
      }
      return (await r.json()) as T;
    } finally {
      clearTimeout(timer);
    }
  }

  async health(): Promise<{ status: string }> {
    return this.request<{ status: string }>(
      `${this.base}/healthz`,
      "GET",
      undefined,
      HEALTH_TIMEOUT_MS
    );
  }

  async healthOrNull(): Promise<{ status: string } | null> {
    try {
      return await this.health();
    } catch {
      return null;
    }
  }

  async verseMarkdown(req: VerseMarkdownRequest): Promise<VerseMarkdownResponse> {
    return this.request<VerseMarkdownResponse>(
      `${this.base}/api/v1/verse_markdown`,
      "POST",
      req
    );
  }

  async crossRefs(req: CrossRefRequest): Promise<CrossRefResponse> {
    return this.request<CrossRefResponse>(
      `${this.base}/api/v1/cross_references`,
      "POST",
      req
    );
  }

  async vaultAppend(req: VaultAppendRequest): Promise<VaultAppendResponse> {
    return this.request<VaultAppendResponse>(
      `${this.base}/api/v1/vault/append`,
      "POST",
      req
    );
  }
}
```

> **Note:** the `${base!r}` token in the constructor message is a typo from a Python idiom; the TypeScript valid form is `${base}`. Replace before commit.

Fix:

```typescript
    if (base !== API_BASE) {
      throw new Error(`JwApiClient refuses non-default base ${base} (only ${API_BASE} allowed)`);
    }
```

- [x] **Step 4: Run test to verify it passes**

Run: `pnpm vitest run tests/unit/api.spec.ts`
Expected: 7 passed.

- [x] **Step 5: Commit**

```bash
git add apps/wol-browser-extension/src/config.ts apps/wol-browser-extension/src/types.ts apps/wol-browser-extension/src/api.ts apps/wol-browser-extension/tests/unit/api.spec.ts
git commit -m "feat(wol-ext): JwApiClient with hard localhost allow-list and explicit errors"
```

---

### Task 3: Verse detector (`src/dom/verse_detector.ts`)

**Files:**
- Create: `apps/wol-browser-extension/src/dom/verse_detector.ts`
- Create: `apps/wol-browser-extension/tests/unit/verse_detector.spec.ts`
- Create: `apps/wol-browser-extension/tests/playwright/fixture_pages/john_3_es.html`

- [x] **Step 1: Write the fixture HTML (minimal repro of WOL DOM)**

```html
<!-- apps/wol-browser-extension/tests/playwright/fixture_pages/john_3_es.html -->
<!doctype html>
<html lang="es">
  <head>
    <meta charset="utf-8" />
    <title>Juan 3 — wol.jw.org fixture</title>
  </head>
  <body>
    <div id="article">
      <h1>Juan 3</h1>
      <p>
        <span id="v43003001" class="verse" data-verse="1"><sup class="verseNum">1</sup>Había un hombre de los fariseos llamado Nicodemo.</span>
        <span id="v43003002" class="verse" data-verse="2"><sup class="verseNum">2</sup>Este vino a Jesús de noche.</span>
        <span id="v43003016" class="verse" data-verse="16"><sup class="verseNum">16</sup>Porque Dios amó tanto al mundo que dio a su Hijo unigénito.</span>
        <span id="v43003036" class="verse" data-verse="36"><sup class="verseNum">36</sup>El que ejerce fe en el Hijo tiene vida eterna.</span>
      </p>
    </div>
  </body>
</html>
```

- [x] **Step 2: Write the failing test**

```typescript
// apps/wol-browser-extension/tests/unit/verse_detector.spec.ts
import { describe, it, expect, beforeEach } from "vitest";
import { detectVerses, buildReferenceFromUrl } from "../../src/dom/verse_detector";

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
      "https://wol.jw.org/es/wol/b/r4/lp-s/nwt/E/2024/43/3"
    );
    expect(ctx).toEqual({ book: "Juan", chapter: 3 });
  });

  it("returns null for a non-bible page", () => {
    expect(
      buildReferenceFromUrl("https://wol.jw.org/es/wol/h/r4/lp-s")
    ).toBeNull();
  });
});
```

- [x] **Step 3: Run test to verify it fails**

Run: `pnpm vitest run tests/unit/verse_detector.spec.ts`
Expected: FAIL — module missing.

- [x] **Step 4: Implement the detector**

```typescript
// apps/wol-browser-extension/src/dom/verse_detector.ts
import type { VerseTarget } from "../types";

export interface ChapterContext {
  /** Localized book name as printed in the URL slug. */
  book: string;
  chapter: number;
}

// Numeric book-id to localized name lookup. Limited to common cases —
// full localization stays server-side; this is only a UI hint, not a parse.
const BOOK_NUM_TO_NAME_ES: Record<number, string> = {
  1: "Génesis",
  43: "Juan",
  45: "Romanos",
  44: "Hechos",
};

const BOOK_NUM_TO_NAME_EN: Record<number, string> = {
  1: "Genesis",
  43: "John",
  44: "Acts",
  45: "Romans",
};

/**
 * Parse a canonical WOL bible URL of the form
 *   https://wol.jw.org/<lang>/wol/b/<rev>/<edition>/<pub>/<bookNum>/<chapter>
 */
export function buildReferenceFromUrl(href: string): ChapterContext | null {
  let url: URL;
  try {
    url = new URL(href);
  } catch {
    return null;
  }
  if (url.hostname !== "wol.jw.org") return null;
  const m = url.pathname.match(
    /\/(?<lang>[a-z]{1,3})\/wol\/b\/r\d+\/[^/]+\/[^/]+\/(?<book>\d{1,2})\/(?<chap>\d{1,3})$/i
  );
  if (!m?.groups) return null;
  const bookNum = Number(m.groups["book"]);
  const chapter = Number(m.groups["chap"]);
  const lang = m.groups["lang"]!.toLowerCase();
  const table = lang === "en" ? BOOK_NUM_TO_NAME_EN : BOOK_NUM_TO_NAME_ES;
  const book = table[bookNum] ?? `[book ${bookNum}]`;
  return { book, chapter };
}

export function detectVerses(
  doc: Document,
  ctx: ChapterContext | null
): VerseTarget[] {
  if (!ctx) return [];
  const out: VerseTarget[] = [];
  for (const node of doc.querySelectorAll<HTMLElement>("span.verse")) {
    const attr = node.getAttribute("data-verse");
    if (!attr) continue;
    const verseNum = Number(attr);
    if (!Number.isFinite(verseNum) || verseNum <= 0) continue;
    out.push({
      verseNum,
      reference: `${ctx.book} ${ctx.chapter}:${verseNum}`,
      node,
    });
  }
  return out;
}
```

- [x] **Step 5: Run test to verify it passes**

Run: `pnpm vitest run tests/unit/verse_detector.spec.ts`
Expected: 6 passed.

- [x] **Step 6: Commit**

```bash
git add apps/wol-browser-extension/src/dom/verse_detector.ts apps/wol-browser-extension/tests/unit/verse_detector.spec.ts apps/wol-browser-extension/tests/playwright/fixture_pages/john_3_es.html
git commit -m "feat(wol-ext): verse detector + URL→chapter parser with golden fixture"
```

---

### Task 4: Button injector + tooltip + styles

**Files:**
- Create: `apps/wol-browser-extension/src/dom/button_injector.ts`
- Create: `apps/wol-browser-extension/src/dom/tooltip.ts`
- Create: `apps/wol-browser-extension/src/dom/styles.css`
- Create: `apps/wol-browser-extension/tests/unit/button_injector.spec.ts`

- [x] **Step 1: Write the failing test**

```typescript
// apps/wol-browser-extension/tests/unit/button_injector.spec.ts
import { describe, it, expect, beforeEach, vi } from "vitest";
import { detectVerses } from "../../src/dom/verse_detector";
import { injectButtonsForVerses } from "../../src/dom/button_injector";

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
      "[data-verse='1'] .jw-ext-btn-explain"
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
    expect(document.querySelectorAll("span.verse")[0]!.textContent).toBe(original);
  });
});
```

- [x] **Step 2: Run test to verify it fails**

Run: `pnpm vitest run tests/unit/button_injector.spec.ts`
Expected: FAIL — module missing.

- [x] **Step 3: Implement injector, tooltip and styles**

```typescript
// apps/wol-browser-extension/src/dom/button_injector.ts
import type { VerseTarget } from "../types";

export interface ButtonHandlers {
  onExplain: (target: VerseTarget) => void;
  onCrossRefs: (target: VerseTarget) => void;
  onSaveVault: (target: VerseTarget) => void;
  t: (key: string) => string;
}

const SENTINEL_CLASS = "jw-ext-verse-actions";
const MARK_ATTR = "data-jw-ext-decorated";

function makeButton(opts: {
  cls: string;
  label: string;
  emoji: string;
  onClick: () => void;
}): HTMLButtonElement {
  const b = document.createElement("button");
  b.type = "button";
  b.className = `jw-ext-btn ${opts.cls}`;
  b.setAttribute("aria-label", opts.label);
  b.title = opts.label;
  b.textContent = opts.emoji;
  b.addEventListener("click", (ev) => {
    ev.preventDefault();
    ev.stopPropagation();
    opts.onClick();
  });
  return b;
}

export function injectButtonsForVerses(
  verses: VerseTarget[],
  handlers: ButtonHandlers
): void {
  for (const target of verses) {
    if (target.node.getAttribute(MARK_ATTR) === "1") continue;
    target.node.setAttribute(MARK_ATTR, "1");

    const wrap = document.createElement("span");
    wrap.className = SENTINEL_CLASS;
    wrap.setAttribute("data-verse", String(target.verseNum));
    wrap.setAttribute("data-reference", target.reference);

    wrap.append(
      makeButton({
        cls: "jw-ext-btn-explain",
        label: handlers.t("action.explain"),
        emoji: "📖",
        onClick: () => handlers.onExplain(target),
      }),
      makeButton({
        cls: "jw-ext-btn-crossrefs",
        label: handlers.t("action.crossrefs"),
        emoji: "🔗",
        onClick: () => handlers.onCrossRefs(target),
      }),
      makeButton({
        cls: "jw-ext-btn-vault",
        label: handlers.t("action.save_vault"),
        emoji: "📝",
        onClick: () => handlers.onSaveVault(target),
      })
    );

    target.node.insertAdjacentElement("afterend", wrap);
  }
}
```

```typescript
// apps/wol-browser-extension/src/dom/tooltip.ts

/**
 * Floating tooltip anchored under an element. Single instance reused.
 * Closes on outside click or Esc.
 */
let current: HTMLElement | null = null;
let escHandler: ((e: KeyboardEvent) => void) | null = null;
let clickHandler: ((e: MouseEvent) => void) | null = null;

function cleanup(): void {
  if (current && current.parentNode) {
    current.parentNode.removeChild(current);
  }
  current = null;
  if (escHandler) {
    document.removeEventListener("keydown", escHandler);
    escHandler = null;
  }
  if (clickHandler) {
    document.removeEventListener("click", clickHandler, true);
    clickHandler = null;
  }
}

export function showTooltip(anchor: HTMLElement, html: string): HTMLElement {
  cleanup();
  const tip = document.createElement("div");
  tip.className = "jw-ext-tooltip";
  tip.innerHTML = html;
  document.body.appendChild(tip);

  const rect = anchor.getBoundingClientRect();
  const top = rect.bottom + window.scrollY + 6;
  const left = Math.max(8, rect.left + window.scrollX);
  tip.style.top = `${top}px`;
  tip.style.left = `${left}px`;

  escHandler = (e: KeyboardEvent) => {
    if (e.key === "Escape") cleanup();
  };
  clickHandler = (e: MouseEvent) => {
    if (!tip.contains(e.target as Node) && e.target !== anchor) cleanup();
  };
  document.addEventListener("keydown", escHandler);
  document.addEventListener("click", clickHandler, true);

  current = tip;
  return tip;
}

export function hideTooltip(): void {
  cleanup();
}

export function showToast(message: string, kind: "ok" | "err" = "ok"): void {
  const t = document.createElement("div");
  t.className = `jw-ext-toast jw-ext-toast-${kind}`;
  t.textContent = message;
  document.body.appendChild(t);
  setTimeout(() => t.classList.add("jw-ext-toast-visible"), 10);
  setTimeout(() => {
    t.classList.remove("jw-ext-toast-visible");
    setTimeout(() => t.remove(), 300);
  }, 3500);
}
```

```css
/* apps/wol-browser-extension/src/dom/styles.css */
.jw-ext-verse-actions {
  display: inline-flex;
  gap: 2px;
  margin-left: 6px;
  vertical-align: middle;
  opacity: 0.45;
  transition: opacity 120ms ease-in-out;
}

.jw-ext-verse-actions:hover,
span.verse:hover + .jw-ext-verse-actions {
  opacity: 1;
}

.jw-ext-btn {
  background: transparent;
  border: 1px solid transparent;
  border-radius: 4px;
  cursor: pointer;
  font-size: 0.78em;
  line-height: 1;
  padding: 1px 4px;
}

.jw-ext-btn:hover {
  border-color: #c0c4cc;
  background: #f5f6f8;
}

.jw-ext-btn:focus-visible {
  outline: 2px solid #2563eb;
  outline-offset: 1px;
}

.jw-ext-tooltip {
  position: absolute;
  z-index: 2147483646;
  max-width: 480px;
  background: #ffffff;
  color: #1f2937;
  border: 1px solid #d1d5db;
  border-radius: 8px;
  box-shadow: 0 10px 25px rgba(0, 0, 0, 0.12);
  padding: 12px 14px;
  font-family: system-ui, -apple-system, sans-serif;
  font-size: 14px;
  line-height: 1.4;
}

.jw-ext-tooltip h3 {
  margin: 0 0 6px;
  font-size: 14px;
  font-weight: 600;
}

.jw-ext-toast {
  position: fixed;
  bottom: 24px;
  left: 50%;
  transform: translateX(-50%) translateY(20px);
  background: #111827;
  color: #f9fafb;
  padding: 8px 14px;
  border-radius: 6px;
  font-family: system-ui, sans-serif;
  font-size: 13px;
  opacity: 0;
  transition: opacity 200ms ease, transform 200ms ease;
  z-index: 2147483647;
}

.jw-ext-toast-err {
  background: #991b1b;
}

.jw-ext-toast-visible {
  opacity: 1;
  transform: translateX(-50%) translateY(0);
}
```

- [x] **Step 4: Run test to verify it passes**

Run: `pnpm vitest run tests/unit/button_injector.spec.ts`
Expected: 5 passed.

- [x] **Step 5: Commit**

```bash
git add apps/wol-browser-extension/src/dom/button_injector.ts apps/wol-browser-extension/src/dom/tooltip.ts apps/wol-browser-extension/src/dom/styles.css apps/wol-browser-extension/tests/unit/button_injector.spec.ts
git commit -m "feat(wol-ext): idempotent button injector + tooltip/toast helpers + prefixed CSS"
```

---

### Task 5: i18n loader

**Files:**
- Create: `apps/wol-browser-extension/src/i18n/index.ts`
- Create: `apps/wol-browser-extension/src/i18n/en.json`
- Create: `apps/wol-browser-extension/src/i18n/es.json`
- Create: `apps/wol-browser-extension/src/i18n/pt.json`
- Create: `apps/wol-browser-extension/tests/unit/i18n.spec.ts`

- [x] **Step 1: Write the failing test**

```typescript
// apps/wol-browser-extension/tests/unit/i18n.spec.ts
import { describe, it, expect } from "vitest";
import { createTranslator, detectLanguage } from "../../src/i18n";

describe("i18n", () => {
  it("returns es translation when language is es", () => {
    const t = createTranslator("es");
    expect(t("action.explain")).toMatch(/explica/i);
  });

  it("falls back to en when language is unknown", () => {
    const t = createTranslator("xx" as any);
    expect(t("action.explain")).toMatch(/explain/i);
  });

  it("returns the key itself when message is missing", () => {
    const t = createTranslator("en");
    expect(t("missing.thing.xyz")).toBe("missing.thing.xyz");
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
```

- [x] **Step 2: Run test to verify it fails**

Run: `pnpm vitest run tests/unit/i18n.spec.ts`
Expected: FAIL — module missing.

- [x] **Step 3: Implement i18n + locale files**

```json
// apps/wol-browser-extension/src/i18n/en.json
{
  "action.explain": "Explain this verse",
  "action.crossrefs": "Cross-references",
  "action.save_vault": "Save to Obsidian",
  "popup.title": "JW Toolkit — WOL Companion",
  "popup.vault_path": "Obsidian vault path",
  "popup.vault_path_placeholder": "/Users/you/Documents/Vault",
  "popup.test_connection": "Test connection",
  "popup.toolkit_ok": "Toolkit running ✓",
  "popup.toolkit_off": "Toolkit not running. Run `jw mcp serve` in a terminal.",
  "popup.language": "Language",
  "popup.save": "Save",
  "popup.saved": "Saved.",
  "toast.saved": "Saved to {path}",
  "toast.error": "Error: {msg}"
}
```

```json
// apps/wol-browser-extension/src/i18n/es.json
{
  "action.explain": "Explicar este versículo",
  "action.crossrefs": "Referencias cruzadas",
  "action.save_vault": "Guardar en Obsidian",
  "popup.title": "JW Toolkit — WOL Companion",
  "popup.vault_path": "Ruta del vault de Obsidian",
  "popup.vault_path_placeholder": "/Users/tu/Documents/Vault",
  "popup.test_connection": "Probar conexión",
  "popup.toolkit_ok": "Toolkit activo ✓",
  "popup.toolkit_off": "El toolkit no responde. Ejecuta `jw mcp serve`.",
  "popup.language": "Idioma",
  "popup.save": "Guardar",
  "popup.saved": "Guardado.",
  "toast.saved": "Guardado en {path}",
  "toast.error": "Error: {msg}"
}
```

```json
// apps/wol-browser-extension/src/i18n/pt.json
{
  "action.explain": "Explicar este versículo",
  "action.crossrefs": "Referências cruzadas",
  "action.save_vault": "Salvar no Obsidian",
  "popup.title": "JW Toolkit — WOL Companion",
  "popup.vault_path": "Caminho do vault do Obsidian",
  "popup.vault_path_placeholder": "/Users/voce/Documents/Vault",
  "popup.test_connection": "Testar conexão",
  "popup.toolkit_ok": "Toolkit ativo ✓",
  "popup.toolkit_off": "Toolkit fora do ar. Rode `jw mcp serve`.",
  "popup.language": "Idioma",
  "popup.save": "Salvar",
  "popup.saved": "Salvo.",
  "toast.saved": "Salvo em {path}",
  "toast.error": "Erro: {msg}"
}
```

```typescript
// apps/wol-browser-extension/src/i18n/index.ts
import en from "./en.json";
import es from "./es.json";
import pt from "./pt.json";
import type { Language } from "../types";

type Messages = Record<string, string>;

const TABLES: Record<Language, Messages> = {
  en: en as Messages,
  es: es as Messages,
  pt: pt as Messages,
};

export function createTranslator(lang: Language) {
  const dict = TABLES[lang] ?? TABLES.en;
  return function t(key: string, params: Record<string, string> = {}): string {
    const raw = dict[key] ?? TABLES.en[key] ?? key;
    return raw.replace(/\{(\w+)\}/g, (_, k: string) => params[k] ?? `{${k}}`);
  };
}

const URL_LANG_MAP: Record<string, Language> = {
  en: "en",
  es: "es",
  t: "pt", // wol uses /t/ for Portuguese
  pt: "pt",
};

export function detectLanguage(href: string): Language {
  try {
    const u = new URL(href);
    const seg = u.pathname.split("/").filter(Boolean)[0] ?? "en";
    return URL_LANG_MAP[seg] ?? "en";
  } catch {
    return "en";
  }
}
```

- [x] **Step 4: Run test to verify it passes**

Run: `pnpm vitest run tests/unit/i18n.spec.ts`
Expected: 5 passed.

- [x] **Step 5: Commit**

```bash
git add apps/wol-browser-extension/src/i18n apps/wol-browser-extension/tests/unit/i18n.spec.ts
git commit -m "feat(wol-ext): i18n en/es/pt with URL-based detection and en fallback"
```

---

### Task 6: Content script wiring

**Files:**
- Create: `apps/wol-browser-extension/src/content_script.ts`
- Create: `apps/wol-browser-extension/src/background.ts`

- [x] **Step 1: Write the content_script smoke test (DOM only)**

```typescript
// apps/wol-browser-extension/tests/unit/content_script.spec.ts
import { describe, it, expect, vi, beforeEach } from "vitest";
import { run } from "../../src/content_script";

const HTML = `
  <p>
    <span class="verse" data-verse="1"><sup class="verseNum">1</sup>uno</span>
    <span class="verse" data-verse="2"><sup class="verseNum">2</sup>dos</span>
  </p>
`;

describe("content_script.run", () => {
  beforeEach(() => {
    document.body.innerHTML = HTML;
    // jsdom URL handling
    Object.defineProperty(window, "location", {
      value: new URL("https://wol.jw.org/es/wol/b/r4/lp-s/nwt/E/2024/43/3"),
      writable: true,
    });
  });

  it("injects buttons when chapter context can be derived", () => {
    const explain = vi.fn();
    run({
      onExplain: explain,
      onCrossRefs: vi.fn(),
      onSaveVault: vi.fn(),
      now: () => 0,
    });
    expect(document.querySelectorAll(".jw-ext-verse-actions")).toHaveLength(2);
  });

  it("is a no-op on a non-bible URL", () => {
    Object.defineProperty(window, "location", {
      value: new URL("https://wol.jw.org/es/wol/h/r4/lp-s"),
      writable: true,
    });
    run({
      onExplain: vi.fn(),
      onCrossRefs: vi.fn(),
      onSaveVault: vi.fn(),
      now: () => 0,
    });
    expect(document.querySelectorAll(".jw-ext-verse-actions")).toHaveLength(0);
  });
});
```

- [x] **Step 2: Run test to verify it fails**

Run: `pnpm vitest run tests/unit/content_script.spec.ts`
Expected: FAIL — module missing.

- [x] **Step 3: Implement content_script and background**

```typescript
// apps/wol-browser-extension/src/content_script.ts
import { JwApiClient } from "./api";
import { injectButtonsForVerses } from "./dom/button_injector";
import { showTooltip, showToast } from "./dom/tooltip";
import { detectVerses, buildReferenceFromUrl } from "./dom/verse_detector";
import { createTranslator, detectLanguage } from "./i18n";
import type { Language, VerseTarget } from "./types";

interface RunOpts {
  onExplain?: (t: VerseTarget) => void;
  onCrossRefs?: (t: VerseTarget) => void;
  onSaveVault?: (t: VerseTarget) => void;
  now?: () => number;
}

async function getStoredVaultPath(): Promise<string | null> {
  if (typeof chrome === "undefined" || !chrome.storage?.local) return null;
  const data = await chrome.storage.local.get(["vault_path"]);
  return typeof data.vault_path === "string" ? data.vault_path : null;
}

async function getStoredLanguage(fallback: Language): Promise<Language> {
  if (typeof chrome === "undefined" || !chrome.storage?.local) return fallback;
  const data = await chrome.storage.local.get(["language"]);
  return (data.language as Language | undefined) ?? fallback;
}

function defaultHandlers(t: (k: string, p?: Record<string, string>) => string) {
  const api = new JwApiClient();

  return {
    onExplain: async (target: VerseTarget) => {
      const lang = await getStoredLanguage(detectLanguage(window.location.href));
      const anchor =
        (target.node.nextElementSibling as HTMLElement | null) ?? target.node;
      showTooltip(anchor, `<em>${t("action.explain")}…</em>`);
      try {
        const out = await api.verseMarkdown({
          reference: target.reference,
          language: lang,
          template: "callout",
        });
        showTooltip(anchor, `<h3>${target.reference}</h3><pre>${out.markdown}</pre>`);
      } catch (err) {
        showToast(
          t("toast.error", { msg: err instanceof Error ? err.message : "unknown" }),
          "err"
        );
      }
    },
    onCrossRefs: async (target: VerseTarget) => {
      const lang = await getStoredLanguage(detectLanguage(window.location.href));
      const anchor =
        (target.node.nextElementSibling as HTMLElement | null) ?? target.node;
      showTooltip(anchor, `<em>${t("action.crossrefs")}…</em>`);
      try {
        const out = await api.crossRefs({ reference: target.reference, language: lang });
        const items = out.refs
          .map(
            (r) =>
              `<li><a href="${r.url}" target="_blank" rel="noopener">${r.verse}</a>${
                r.excerpt ? `: ${r.excerpt}` : ""
              }</li>`
          )
          .join("");
        showTooltip(
          anchor,
          `<h3>${target.reference}</h3><ul>${items || "<li>—</li>"}</ul>`
        );
      } catch (err) {
        showToast(
          t("toast.error", { msg: err instanceof Error ? err.message : "unknown" }),
          "err"
        );
      }
    },
    onSaveVault: async (target: VerseTarget) => {
      const lang = await getStoredLanguage(detectLanguage(window.location.href));
      const vaultPath = await getStoredVaultPath();
      if (!vaultPath) {
        showToast(
          t("toast.error", { msg: "vault path not configured" }),
          "err"
        );
        return;
      }
      try {
        const out = await api.vaultAppend({
          reference: target.reference,
          vault_path: vaultPath,
          template: "callout",
          language: lang,
        });
        if (out.ok) {
          showToast(t("toast.saved", { path: out.path }));
        } else {
          showToast(t("toast.error", { msg: out.error ?? "unknown" }), "err");
        }
      } catch (err) {
        showToast(
          t("toast.error", { msg: err instanceof Error ? err.message : "unknown" }),
          "err"
        );
      }
    },
  };
}

export function run(opts: RunOpts = {}): void {
  const ctx = buildReferenceFromUrl(window.location.href);
  if (!ctx) return;

  const lang = detectLanguage(window.location.href);
  const t = createTranslator(lang);
  const verses = detectVerses(document, ctx);
  if (verses.length === 0) return;

  const handlers = defaultHandlers(t);

  injectButtonsForVerses(verses, {
    onExplain: opts.onExplain ?? handlers.onExplain,
    onCrossRefs: opts.onCrossRefs ?? handlers.onCrossRefs,
    onSaveVault: opts.onSaveVault ?? handlers.onSaveVault,
    t,
  });

  console.info(`[jw-ext] injected ${verses.length} verse action(s)`);
}

// Auto-run when bundled into the page. Vitest imports `run` directly.
if (typeof window !== "undefined" && window.location?.hostname === "wol.jw.org") {
  if (document.readyState === "complete" || document.readyState === "interactive") {
    run();
  } else {
    document.addEventListener("DOMContentLoaded", () => run());
  }
}
```

```typescript
// apps/wol-browser-extension/src/background.ts
import { JwApiClient } from "./api";

const api = new JwApiClient();

async function pollHealth(): Promise<void> {
  const ok = await api.healthOrNull();
  if (typeof chrome === "undefined" || !chrome.action) return;
  if (ok) {
    chrome.action.setBadgeText({ text: "" });
    chrome.action.setTitle({ title: "JW Toolkit — connected" });
  } else {
    chrome.action.setBadgeText({ text: "off" });
    chrome.action.setBadgeBackgroundColor({ color: "#9ca3af" });
    chrome.action.setTitle({
      title: "JW Toolkit not running. Run `jw mcp serve`.",
    });
  }
}

chrome.runtime.onInstalled.addListener(() => {
  void pollHealth();
});

// On every tab update to a wol.jw.org page, re-check health (cheap, local).
chrome.tabs?.onUpdated.addListener((_id, info, tab) => {
  if (info.status === "complete" && tab.url?.startsWith("https://wol.jw.org/")) {
    void pollHealth();
  }
});

// Surface a manual health refresh for the popup.
chrome.runtime.onMessage.addListener((msg, _sender, sendResponse) => {
  if (msg?.kind === "health") {
    api.healthOrNull().then((v) => sendResponse({ ok: !!v }));
    return true; // keep channel open for async response
  }
  return false;
});
```

- [x] **Step 4: Run test to verify it passes**

Run: `pnpm vitest run tests/unit/content_script.spec.ts`
Expected: 2 passed.

- [x] **Step 5: Commit**

```bash
git add apps/wol-browser-extension/src/content_script.ts apps/wol-browser-extension/src/background.ts apps/wol-browser-extension/tests/unit/content_script.spec.ts
git commit -m "feat(wol-ext): content_script wires detector→injector→tooltip + background health-check"
```

---

### Task 7: Popup UI for settings

**Files:**
- Create: `apps/wol-browser-extension/src/popup/popup.html`
- Create: `apps/wol-browser-extension/src/popup/popup.ts`
- Create: `apps/wol-browser-extension/src/popup/popup.css`

- [x] **Step 1: Write the failing test**

```typescript
// apps/wol-browser-extension/tests/unit/popup.spec.ts
import { describe, it, expect, beforeEach, vi } from "vitest";
import { renderPopup, savePopupSettings } from "../../src/popup/popup";

describe("popup", () => {
  beforeEach(() => {
    document.body.innerHTML = `
      <div id="root"></div>
    `;
    // Minimal chrome.storage stub.
    (globalThis as any).chrome = {
      storage: {
        local: {
          _store: {},
          get: vi.fn(function (this: any, keys: string[]) {
            const out: Record<string, unknown> = {};
            for (const k of keys) out[k] = this._store[k];
            return Promise.resolve(out);
          }),
          set: vi.fn(function (this: any, obj: Record<string, unknown>) {
            Object.assign(this._store, obj);
            return Promise.resolve();
          }),
        },
      },
      runtime: { sendMessage: vi.fn(() => Promise.resolve({ ok: true })) },
    };
  });

  it("renders inputs and labels", async () => {
    await renderPopup(document.getElementById("root")!, "en");
    expect(document.querySelector("#vault_path")).not.toBeNull();
    expect(document.querySelector("#language")).not.toBeNull();
    expect(document.querySelector("#save")).not.toBeNull();
  });

  it("savePopupSettings writes to chrome.storage.local", async () => {
    await savePopupSettings({ vault_path: "/x/vault", language: "es" });
    const storage = (globalThis as any).chrome.storage.local;
    expect(storage.set).toHaveBeenCalledWith({
      vault_path: "/x/vault",
      language: "es",
    });
  });
});
```

- [x] **Step 2: Run test to verify it fails**

Run: `pnpm vitest run tests/unit/popup.spec.ts`
Expected: FAIL — module missing.

- [x] **Step 3: Implement popup**

```html
<!-- apps/wol-browser-extension/src/popup/popup.html -->
<!doctype html>
<html>
  <head>
    <meta charset="utf-8" />
    <title>JW Toolkit — WOL</title>
    <link rel="stylesheet" href="popup.css" />
  </head>
  <body>
    <div id="root"></div>
    <script type="module" src="popup.ts"></script>
  </body>
</html>
```

```css
/* apps/wol-browser-extension/src/popup/popup.css */
:root {
  color-scheme: light;
}

body {
  margin: 0;
  width: 320px;
  font-family: system-ui, -apple-system, sans-serif;
  font-size: 13px;
  color: #1f2937;
}

#root {
  padding: 14px;
}

h1 {
  margin: 0 0 12px;
  font-size: 14px;
  font-weight: 600;
}

label {
  display: block;
  margin-top: 10px;
  font-weight: 500;
  font-size: 12px;
}

input[type="text"],
select {
  width: 100%;
  padding: 6px 8px;
  border: 1px solid #d1d5db;
  border-radius: 4px;
  font-size: 13px;
  box-sizing: border-box;
}

button {
  margin-top: 12px;
  padding: 7px 14px;
  border: none;
  border-radius: 4px;
  background: #2563eb;
  color: white;
  cursor: pointer;
  font-weight: 500;
}

button:hover {
  background: #1d4ed8;
}

.status {
  margin-top: 8px;
  font-size: 12px;
}

.status-ok {
  color: #047857;
}

.status-err {
  color: #b91c1c;
}
```

```typescript
// apps/wol-browser-extension/src/popup/popup.ts
import { createTranslator } from "../i18n";
import type { Language } from "../types";

interface Settings {
  vault_path: string;
  language: Language;
}

async function loadSettings(): Promise<Settings> {
  const data = await chrome.storage.local.get(["vault_path", "language"]);
  return {
    vault_path: typeof data.vault_path === "string" ? data.vault_path : "",
    language: (data.language as Language | undefined) ?? "en",
  };
}

export async function savePopupSettings(s: Settings): Promise<void> {
  await chrome.storage.local.set({
    vault_path: s.vault_path,
    language: s.language,
  });
}

export async function renderPopup(root: HTMLElement, lang: Language): Promise<void> {
  const t = createTranslator(lang);
  const current = await loadSettings();
  const effectiveLang = current.language || lang;
  const tEff = createTranslator(effectiveLang);

  root.innerHTML = `
    <h1>${tEff("popup.title")}</h1>
    <label for="vault_path">${tEff("popup.vault_path")}</label>
    <input id="vault_path" type="text" placeholder="${tEff(
      "popup.vault_path_placeholder"
    )}" value="${current.vault_path}" />
    <label for="language">${tEff("popup.language")}</label>
    <select id="language">
      <option value="en" ${effectiveLang === "en" ? "selected" : ""}>English</option>
      <option value="es" ${effectiveLang === "es" ? "selected" : ""}>Español</option>
      <option value="pt" ${effectiveLang === "pt" ? "selected" : ""}>Português</option>
    </select>
    <button id="test">${tEff("popup.test_connection")}</button>
    <button id="save">${tEff("popup.save")}</button>
    <div id="status" class="status"></div>
  `;

  const status = root.querySelector<HTMLDivElement>("#status")!;
  root.querySelector<HTMLButtonElement>("#test")!.addEventListener("click", async () => {
    status.textContent = "…";
    status.className = "status";
    const resp = await chrome.runtime.sendMessage({ kind: "health" });
    if (resp?.ok) {
      status.textContent = tEff("popup.toolkit_ok");
      status.className = "status status-ok";
    } else {
      status.textContent = tEff("popup.toolkit_off");
      status.className = "status status-err";
    }
  });

  root.querySelector<HTMLButtonElement>("#save")!.addEventListener("click", async () => {
    const vault = root.querySelector<HTMLInputElement>("#vault_path")!.value.trim();
    const language = root.querySelector<HTMLSelectElement>("#language")!.value as Language;
    await savePopupSettings({ vault_path: vault, language });
    status.textContent = tEff("popup.saved");
    status.className = "status status-ok";
  });
}

// Boot when used as the actual popup (skipped in unit tests).
if (typeof window !== "undefined" && document.getElementById("root")) {
  const browserLang = (navigator.language ?? "en").slice(0, 2) as Language;
  void renderPopup(document.getElementById("root")!, browserLang);
}
```

- [x] **Step 4: Run test to verify it passes**

Run: `pnpm vitest run tests/unit/popup.spec.ts`
Expected: 2 passed.

- [x] **Step 5: Commit**

```bash
git add apps/wol-browser-extension/src/popup apps/wol-browser-extension/tests/unit/popup.spec.ts
git commit -m "feat(wol-ext): popup UI for vault path + language + health check"
```

---

### Task 8: Backend — tighten CORS to explicit origin regex

**Files:**
- Modify: `packages/jw-mcp/src/jw_mcp/rest_api.py`
- Create: `packages/jw-mcp/tests/test_cors_origins.py`

- [x] **Step 1: Write the failing test**

```python
# packages/jw-mcp/tests/test_cors_origins.py
"""Verify CORS is tightened to the wol.jw.org + extension origins.

Replaces the previous `allow_origins=["*"]` permissive default.
"""

from __future__ import annotations

from fastapi.testclient import TestClient

from jw_mcp.rest_api import app


def _client() -> TestClient:
    return TestClient(app)


def test_cors_allows_wol() -> None:
    r = _client().get(
        "/healthz",
        headers={
            "Origin": "https://wol.jw.org",
            "Access-Control-Request-Method": "GET",
        },
    )
    assert r.headers.get("access-control-allow-origin") == "https://wol.jw.org"


def test_cors_allows_chrome_extension() -> None:
    origin = "chrome-extension://abcdefghijklmnopabcdefghijklmnop"
    r = _client().get("/healthz", headers={"Origin": origin})
    assert r.headers.get("access-control-allow-origin") == origin


def test_cors_allows_moz_extension() -> None:
    origin = "moz-extension://11111111-2222-3333-4444-555555555555"
    r = _client().get("/healthz", headers={"Origin": origin})
    assert r.headers.get("access-control-allow-origin") == origin


def test_cors_blocks_random_https_origin() -> None:
    r = _client().get(
        "/healthz", headers={"Origin": "https://attacker.example.com"}
    )
    # Either no ACAO header at all or echoing back is rejected by browser.
    # FastAPI's CORSMiddleware in regex mode omits the header for non-matches.
    assert r.headers.get("access-control-allow-origin") in (None, "")


def test_cors_blocks_http_localhost_from_wrong_port() -> None:
    r = _client().get("/healthz", headers={"Origin": "http://localhost:9999"})
    assert r.headers.get("access-control-allow-origin") in (None, "")


def test_cors_preflight_options() -> None:
    r = _client().options(
        "/api/v1/verse_markdown",
        headers={
            "Origin": "https://wol.jw.org",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "content-type",
        },
    )
    assert r.status_code in (200, 204)
    assert r.headers.get("access-control-allow-origin") == "https://wol.jw.org"
    assert "POST" in (r.headers.get("access-control-allow-methods") or "")
```

- [x] **Step 2: Run test to verify it fails**

Run: `uv run pytest packages/jw-mcp/tests/test_cors_origins.py -v`
Expected: FAIL — current code uses `allow_origins=["*"]`; `test_cors_blocks_*` fail because `*` answers ACAO=`*` for every origin.

- [x] **Step 3: Tighten CORS in `rest_api.py`**

Replace the existing block:

```python
# Permissive CORS — bots may run anywhere; tighten for production.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)
```

with the explicit allow-list:

```python
# CORS — only browser surfaces we own. wol.jw.org for the WOL extension,
# chrome-extension://<id> and moz-extension://<uuid> for the extension
# popup/background. Everything else is denied.
#
# Why regex: chrome.spec disallows wildcard in `allow_origins` (it requires
# exact strings), but starlette's CORSMiddleware supports `allow_origin_regex`
# which validates by pattern at request time and echoes the *requesting*
# origin into ACAO. That's what we want here.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://wol.jw.org"],
    allow_origin_regex=r"^(chrome-extension|moz-extension)://[a-zA-Z0-9\-]+$",
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization"],
)
```

- [x] **Step 4: Run test to verify it passes**

Run: `uv run pytest packages/jw-mcp/tests/test_cors_origins.py -v`
Expected: 6 passed.

- [x] **Step 5: Run full jw-mcp suite to confirm no regression**

Run: `uv run pytest packages/jw-mcp -q`
Expected: all green.

- [x] **Step 6: Commit**

```bash
git add packages/jw-mcp/src/jw_mcp/rest_api.py packages/jw-mcp/tests/test_cors_origins.py
git commit -m "feat(jw-mcp): tighten CORS to wol.jw.org + extension regex (BREAKING vs * default)"
```

---

### Task 9: Backend — `POST /api/v1/cross_references` endpoint

**Files:**
- Modify: `packages/jw-mcp/src/jw_mcp/rest_api.py`
- Create: `packages/jw-mcp/tests/test_cross_references_endpoint.py`

- [x] **Step 1: Write the failing test**

```python
# packages/jw-mcp/tests/test_cross_references_endpoint.py
"""Tests for POST /api/v1/cross_references — used by the WOL extension."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from jw_mcp.rest_api import app


def test_cross_references_returns_list() -> None:
    c = TestClient(app)
    r = c.post(
        "/api/v1/cross_references",
        json={"reference": "Juan 3:16", "language": "es"},
    )
    assert r.status_code == 200
    body = r.json()
    assert "refs" in body
    assert isinstance(body["refs"], list)


def test_cross_references_rejects_bad_reference() -> None:
    c = TestClient(app)
    r = c.post(
        "/api/v1/cross_references",
        json={"reference": "not a reference", "language": "es"},
    )
    assert r.status_code == 200
    body = r.json()
    assert body.get("error") or body.get("refs") == []


def test_cross_references_each_entry_has_url_and_verse() -> None:
    c = TestClient(app)
    r = c.post(
        "/api/v1/cross_references",
        json={"reference": "John 3:16", "language": "en"},
    )
    assert r.status_code == 200
    body = r.json()
    for ref in body.get("refs", []):
        assert "verse" in ref
        assert "url" in ref
        assert ref["url"].startswith("https://wol.jw.org/")
```

- [x] **Step 2: Run test to verify it fails**

Run: `uv run pytest packages/jw-mcp/tests/test_cross_references_endpoint.py -v`
Expected: FAIL — endpoint missing returns 404.

- [x] **Step 3: Add the endpoint and request model**

In `packages/jw-mcp/src/jw_mcp/rest_api.py`, after the existing schemas section, add:

```python
class CrossRefRequest(BaseModel):
    reference: str
    language: str = "en"
    limit: int = 8
```

And after the existing endpoints, add the handler:

```python
@app.post("/api/v1/cross_references")
async def post_cross_references(req: CrossRefRequest) -> dict[str, Any]:
    """Return up to `limit` cross-references for a parsed verse reference.

    Implementation MVP: parse_reference → query the topic-index for the verse
    string → return matched WOL URLs. Empty list if reference invalid or no
    matches; never raises 5xx for shape errors.
    """
    ref = parse_reference(req.reference)
    if ref is None:
        return {"refs": [], "error": f"could not parse reference: {req.reference!r}"}

    wol = _get_wol()
    cdn = _get_cdn()
    lang = get_language(req.language)

    # MVP: search the topic-index/CDN for the verse string and re-rank by language.
    query = ref.display()
    try:
        hits = await cdn.search(
            query,
            filter_type="bibleVerse",
            language=lang.jw_code,
            limit=max(1, min(req.limit, 20)),
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("cross_references search failed: %r", exc)
        return {"refs": [], "error": str(exc)}

    refs: list[dict[str, Any]] = []
    for h in hits or []:
        url = h.get("url") if isinstance(h, dict) else None
        verse = h.get("verse") or h.get("title") if isinstance(h, dict) else None
        excerpt = h.get("snippet") if isinstance(h, dict) else None
        if url and url.startswith("https://wol.jw.org/"):
            refs.append({"verse": verse or query, "url": url, "excerpt": excerpt or ""})

    return {"refs": refs, "reference": ref.display(), "language": req.language}
```

- [x] **Step 4: Run test to verify it passes**

Run: `uv run pytest packages/jw-mcp/tests/test_cross_references_endpoint.py -v`
Expected: 3 passed.

- [x] **Step 5: Commit**

```bash
git add packages/jw-mcp/src/jw_mcp/rest_api.py packages/jw-mcp/tests/test_cross_references_endpoint.py
git commit -m "feat(jw-mcp): POST /api/v1/cross_references endpoint for the WOL extension"
```

---

### Task 10: Backend — `POST /api/v1/vault/append` with **vault path validation**

**Files:**
- Modify: `packages/jw-mcp/src/jw_mcp/rest_api.py`
- Create: `packages/jw-mcp/tests/test_vault_append_endpoint.py`

This task addresses Spec Risk #7 (user points `vaultPath` at `~/.ssh`). The endpoint MUST refuse to write outside an Obsidian vault, detected by the presence of `.obsidian/` somewhere in the path ancestry.

- [x] **Step 1: Write the failing test**

```python
# packages/jw-mcp/tests/test_vault_append_endpoint.py
"""POST /api/v1/vault/append — append a verse markdown block to a vault file.

Critical security property: the path MUST be inside an Obsidian vault
(detected by ancestor directory containing a `.obsidian/` folder).
The endpoint MUST refuse writes to ~/.ssh, /etc, $HOME root, etc.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from jw_mcp.rest_api import app


def _make_fake_vault(root: Path) -> Path:
    """Create a directory that looks like an Obsidian vault."""
    vault = root / "MyVault"
    vault.mkdir()
    (vault / ".obsidian").mkdir()
    (vault / ".obsidian" / "app.json").write_text("{}", encoding="utf-8")
    return vault


def test_vault_append_writes_inside_vault(tmp_path: Path) -> None:
    vault = _make_fake_vault(tmp_path)
    c = TestClient(app)
    r = c.post(
        "/api/v1/vault/append",
        json={
            "reference": "Juan 3:16",
            "vault_path": str(vault),
            "template": "callout",
            "language": "es",
        },
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["ok"] is True
    written = Path(body["path"])
    assert written.exists()
    assert vault in written.parents
    assert "Juan" in written.read_text(encoding="utf-8")


def test_vault_append_refuses_non_vault_path(tmp_path: Path) -> None:
    not_a_vault = tmp_path / "random_dir"
    not_a_vault.mkdir()
    c = TestClient(app)
    r = c.post(
        "/api/v1/vault/append",
        json={
            "reference": "Juan 3:16",
            "vault_path": str(not_a_vault),
            "template": "callout",
            "language": "es",
        },
    )
    assert r.status_code == 400
    assert "obsidian" in r.json()["detail"].lower()


def test_vault_append_refuses_dotssh_lookalike(tmp_path: Path) -> None:
    """Defense against Spec Risk #7."""
    ssh = tmp_path / ".ssh"
    ssh.mkdir()
    (ssh / "id_rsa").write_text("private key", encoding="utf-8")
    c = TestClient(app)
    r = c.post(
        "/api/v1/vault/append",
        json={
            "reference": "Juan 3:16",
            "vault_path": str(ssh),
            "template": "callout",
            "language": "es",
        },
    )
    assert r.status_code == 400


def test_vault_append_refuses_path_traversal(tmp_path: Path) -> None:
    vault = _make_fake_vault(tmp_path)
    # Use ".." to try to escape outside the vault via subdir param.
    c = TestClient(app)
    r = c.post(
        "/api/v1/vault/append",
        json={
            "reference": "Juan 3:16",
            "vault_path": str(vault),
            "subdir": "../../../../etc",
            "template": "callout",
            "language": "es",
        },
    )
    assert r.status_code == 400
    assert "outside" in r.json()["detail"].lower() or "traversal" in r.json()["detail"].lower()


def test_vault_append_refuses_root_path() -> None:
    c = TestClient(app)
    r = c.post(
        "/api/v1/vault/append",
        json={
            "reference": "Juan 3:16",
            "vault_path": "/",
            "template": "callout",
            "language": "es",
        },
    )
    assert r.status_code == 400


def test_vault_append_creates_subdir_when_missing(tmp_path: Path) -> None:
    vault = _make_fake_vault(tmp_path)
    c = TestClient(app)
    r = c.post(
        "/api/v1/vault/append",
        json={
            "reference": "John 3:16",
            "vault_path": str(vault),
            "subdir": "Verses",
            "template": "callout",
            "language": "en",
        },
    )
    assert r.status_code == 200
    body = r.json()
    written = Path(body["path"])
    assert "Verses" in written.parts
```

- [x] **Step 2: Run test to verify it fails**

Run: `uv run pytest packages/jw-mcp/tests/test_vault_append_endpoint.py -v`
Expected: 6 FAIL — endpoint missing.

- [x] **Step 3: Implement the endpoint with validation**

Add to `packages/jw-mcp/src/jw_mcp/rest_api.py`:

```python
from fastapi import HTTPException
from pathlib import Path as _Path


class VaultAppendRequest(BaseModel):
    reference: str
    vault_path: str
    template: str = "callout"
    language: str = "en"
    subdir: str = "Verses"
    length: str = "medium"
    publication: str = "nwtsty"


def _resolve_safe(vault_path: str, subdir: str) -> tuple[_Path, _Path]:
    """Return (vault, target_dir).

    Validates:
      - vault_path resolves to an existing directory.
      - vault_path or one of its ancestors contains a `.obsidian/` directory.
      - target_dir, after resolving symlinks and `..`, is *inside* vault.
      - vault_path is not `/`, `$HOME`, or `~` literal.
    """
    if not vault_path or vault_path in {"/", "~"}:
        raise HTTPException(status_code=400, detail="vault_path may not be a root path")

    vault = _Path(vault_path).expanduser().resolve(strict=False)
    if not vault.exists() or not vault.is_dir():
        raise HTTPException(status_code=400, detail=f"vault_path does not exist: {vault}")

    # Walk vault and ancestors looking for `.obsidian/`. Stop at filesystem root.
    has_marker = False
    for candidate in (vault, *vault.parents):
        if (candidate / ".obsidian").is_dir():
            has_marker = True
            # Treat the marker holder as the actual vault root.
            vault = candidate
            break
    if not has_marker:
        raise HTTPException(
            status_code=400,
            detail=(
                "vault_path is not inside an Obsidian vault "
                "(no `.obsidian/` marker found in ancestry)"
            ),
        )

    target_dir = (vault / subdir).resolve(strict=False)
    try:
        target_dir.relative_to(vault)
    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=f"subdir resolves outside vault (path traversal): {subdir!r}",
        ) from exc

    return vault, target_dir


def _safe_filename(ref_display: str) -> str:
    """Convert a reference like 'Juan 3:16' to a filesystem-safe filename."""
    return ref_display.replace(":", "_").replace(" ", "_").replace("/", "-") + ".md"


@app.post("/api/v1/vault/append")
async def post_vault_append(req: VaultAppendRequest) -> dict[str, Any]:
    """Append (or create) a markdown file in the user's vault with the verse block.

    Security:
      - Refuses if vault_path is not within an Obsidian vault.
      - Refuses subdir values that escape the vault via `..`.
      - File is created with mode 0o644.
    """
    ref = parse_reference(req.reference)
    if ref is None:
        raise HTTPException(status_code=400, detail=f"unparseable reference: {req.reference!r}")

    vault, target_dir = _resolve_safe(req.vault_path, req.subdir)
    target_dir.mkdir(parents=True, exist_ok=True)

    # Fetch verse text (best-effort).
    verse_text = ""
    source_url = ""
    if ref.verse_start is not None:
        wol = _get_wol()
        try:
            url, html = await wol.get_bible_chapter(
                ref.book_num, ref.chapter, language=req.language, publication=req.publication
            )
            v = get_verse(html, ref.book_num, ref.chapter, ref.verse_start, language=req.language)
            verse_text = v.text if v else ""
            source_url = url
        except Exception as exc:  # noqa: BLE001
            logger.warning("vault_append: verse fetch failed: %r", exc)

    md = render_verse_block(
        ref,
        verse_text,
        template=req.template,  # type: ignore[arg-type]
        length=req.length,  # type: ignore[arg-type]
        language=req.language,
    )

    fname = _safe_filename(ref.display())
    target = target_dir / fname

    block = f"{md}\n\n<!-- jw-ext source: {source_url} -->\n"
    if target.exists():
        # Append a separator + new block.
        with target.open("a", encoding="utf-8") as fh:
            fh.write("\n\n---\n\n")
            fh.write(block)
    else:
        target.write_text(block, encoding="utf-8")

    return {
        "ok": True,
        "path": str(target),
        "vault": str(vault),
        "reference": ref.display(),
    }
```

- [x] **Step 4: Run test to verify it passes**

Run: `uv run pytest packages/jw-mcp/tests/test_vault_append_endpoint.py -v`
Expected: 6 passed.

- [x] **Step 5: Commit**

```bash
git add packages/jw-mcp/src/jw_mcp/rest_api.py packages/jw-mcp/tests/test_vault_append_endpoint.py
git commit -m "feat(jw-mcp): POST /api/v1/vault/append with .obsidian/ marker + path-traversal guard"
```

---

### Task 11: ESLint hard-rule: no fetch to non-`API_BASE` URLs

**Files:**
- Create: `apps/wol-browser-extension/.eslintrc.cjs`
- Create: `apps/wol-browser-extension/tests/unit/no_external_calls.spec.ts`

- [x] **Step 1: Write the failing static check test**

```typescript
// apps/wol-browser-extension/tests/unit/no_external_calls.spec.ts
import { describe, it, expect } from "vitest";
import { readFileSync, readdirSync, statSync } from "node:fs";
import { join } from "node:path";

const SRC = new URL("../../src", import.meta.url).pathname;
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
        // Strip comments (single-line) for fairness; block comments rare.
        const code = ln.replace(/\/\/.*$/, "");
        for (const match of code.matchAll(re)) {
          const url = match[0];
          if (url.startsWith(ALLOWED_HOST_LITERAL)) continue;
          // wol.jw.org URLs are only allowed in i18n + as types in comments → strip comments handles most.
          if (url.startsWith("https://wol.jw.org/") && f.includes("verse_detector")) continue;
          violations.push({ file: f, line: i + 1, text: ln.trim() });
        }
      });
    }
    expect(violations, JSON.stringify(violations, null, 2)).toEqual([]);
  });
});
```

- [x] **Step 2: Run the test to confirm it passes for current src**

Run: `pnpm vitest run tests/unit/no_external_calls.spec.ts`
Expected: passes (only `verse_detector.ts` may contain `wol.jw.org` in a literal regex; we whitelist that path explicitly).

- [x] **Step 3: Add ESLint rule for runtime fetch guards**

```javascript
// apps/wol-browser-extension/.eslintrc.cjs
module.exports = {
  root: true,
  parser: "@typescript-eslint/parser",
  parserOptions: { ecmaVersion: 2022, sourceType: "module", project: "./tsconfig.json" },
  plugins: ["@typescript-eslint", "no-restricted-syntax"],
  env: { browser: true, node: false, webextensions: true, es2022: true },
  rules: {
    "@typescript-eslint/no-explicit-any": "warn",
    "no-restricted-syntax": [
      "error",
      {
        // Disallow direct `fetch(...)` calls; force routing through JwApiClient.
        selector: "CallExpression[callee.name='fetch']",
        message: "Direct fetch() is forbidden. Use JwApiClient from src/api.ts.",
      },
      {
        selector:
          "Literal[value=/^https?:\\/\\/(?!localhost:8765).*/]",
        message: "External URL literal forbidden. Only http://localhost:8765 is allowed.",
      },
    ],
  },
  overrides: [
    {
      // The api module is the SOLE place fetch is allowed.
      files: ["src/api.ts"],
      rules: { "no-restricted-syntax": "off" },
    },
    {
      // Tests, fixtures, and verse_detector regex need https://wol.jw.org/ literals.
      files: ["tests/**", "src/dom/verse_detector.ts", "src/i18n/**"],
      rules: { "no-restricted-syntax": "off" },
    },
  ],
};
```

- [x] **Step 4: Run lint to confirm it passes**

Run: `pnpm lint`
Expected: 0 errors.

- [x] **Step 5: Commit**

```bash
git add apps/wol-browser-extension/.eslintrc.cjs apps/wol-browser-extension/tests/unit/no_external_calls.spec.ts
git commit -m "feat(wol-ext): eslint rule + static test forbidding non-localhost URLs in src"
```

---

### Task 12: Playwright E2E — extension loaded against mocked WOL page

**Files:**
- Create: `apps/wol-browser-extension/tests/playwright/playwright.config.ts`
- Create: `apps/wol-browser-extension/tests/playwright/mock_backend.ts`
- Create: `apps/wol-browser-extension/tests/playwright/extension.spec.ts`
- Create: `apps/wol-browser-extension/tests/playwright/fixture_pages/john_3_en.html`

- [x] **Step 1: Build the dist bundle (needed by Playwright)**

```bash
cd apps/wol-browser-extension
pnpm build
```
Expected: `dist/` directory created with `manifest.json` + bundled scripts.

- [x] **Step 2: Write Playwright config**

```typescript
// apps/wol-browser-extension/tests/playwright/playwright.config.ts
import { defineConfig } from "@playwright/test";

export default defineConfig({
  testDir: ".",
  timeout: 30_000,
  fullyParallel: false, // extension launch holds a unique user-data-dir
  reporter: [["list"]],
  use: {
    headless: false, // chrome extensions don't load in headless v3 reliably
    viewport: { width: 1280, height: 800 },
  },
  projects: [
    {
      name: "chromium-with-extension",
      use: { browserName: "chromium" },
    },
  ],
});
```

- [x] **Step 3: Write the mock backend**

```typescript
// apps/wol-browser-extension/tests/playwright/mock_backend.ts
import { createServer, Server } from "node:http";
import { AddressInfo } from "node:net";

export interface RecordedRequest {
  url: string;
  method: string;
  origin?: string;
  body?: unknown;
}

export interface MockBackend {
  server: Server;
  port: number;
  requests: RecordedRequest[];
  stop: () => Promise<void>;
}

export async function startMockBackend(port = 8765): Promise<MockBackend> {
  const recorded: RecordedRequest[] = [];
  const server = createServer((req, res) => {
    const chunks: Buffer[] = [];
    req.on("data", (c) => chunks.push(Buffer.from(c)));
    req.on("end", () => {
      const raw = Buffer.concat(chunks).toString("utf-8");
      let body: unknown = undefined;
      try {
        body = raw ? JSON.parse(raw) : undefined;
      } catch {
        body = raw;
      }
      recorded.push({
        url: req.url ?? "",
        method: req.method ?? "",
        origin: req.headers.origin as string | undefined,
        body,
      });

      // CORS preflight
      if (req.method === "OPTIONS") {
        res.writeHead(204, {
          "Access-Control-Allow-Origin": (req.headers.origin as string) ?? "*",
          "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
          "Access-Control-Allow-Headers": "Content-Type",
        });
        res.end();
        return;
      }

      const cors = {
        "Access-Control-Allow-Origin": (req.headers.origin as string) ?? "*",
        "Content-Type": "application/json",
      };

      if (req.url === "/healthz") {
        res.writeHead(200, cors);
        res.end(JSON.stringify({ status: "ok" }));
        return;
      }
      if (req.url === "/api/v1/verse_markdown") {
        res.writeHead(200, cors);
        res.end(
          JSON.stringify({
            markdown:
              "> [!quote] Juan 3:16\n> Porque Dios amó tanto al mundo que dio a su Hijo unigénito.",
            reference: "Juan 3:16",
            language: "es",
            source_url: "https://wol.jw.org/es/wol/b/r4/lp-s/nwt/E/2024/43/3",
          })
        );
        return;
      }
      if (req.url === "/api/v1/cross_references") {
        res.writeHead(200, cors);
        res.end(
          JSON.stringify({
            refs: [
              { verse: "Juan 1:1", url: "https://wol.jw.org/es/x/1", excerpt: "En el principio" },
              { verse: "1 Juan 4:9", url: "https://wol.jw.org/es/x/2", excerpt: "Amor de Dios" },
            ],
          })
        );
        return;
      }
      if (req.url === "/api/v1/vault/append") {
        res.writeHead(200, cors);
        res.end(JSON.stringify({ ok: true, path: "/tmp/vault/Verses/Juan_3_16.md" }));
        return;
      }
      res.writeHead(404, cors);
      res.end(JSON.stringify({ error: "not_found", url: req.url }));
    });
  });
  await new Promise<void>((resolve) => server.listen(port, "127.0.0.1", () => resolve()));
  const actualPort = (server.address() as AddressInfo).port;
  return {
    server,
    port: actualPort,
    requests: recorded,
    stop: () =>
      new Promise<void>((resolve, reject) =>
        server.close((err) => (err ? reject(err) : resolve()))
      ),
  };
}
```

- [x] **Step 4: Write the John 3 English fixture**

```html
<!-- apps/wol-browser-extension/tests/playwright/fixture_pages/john_3_en.html -->
<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8" />
    <title>John 3 — wol.jw.org fixture</title>
  </head>
  <body>
    <div id="article">
      <h1>John 3</h1>
      <p>
        <span class="verse" data-verse="1"><sup class="verseNum">1</sup>There was a man of the Pharisees.</span>
        <span class="verse" data-verse="16"><sup class="verseNum">16</sup>For God loved the world so much.</span>
        <span class="verse" data-verse="36"><sup class="verseNum">36</sup>The one who exercises faith in the Son has everlasting life.</span>
      </p>
    </div>
  </body>
</html>
```

- [x] **Step 5: Write the failing E2E test**

```typescript
// apps/wol-browser-extension/tests/playwright/extension.spec.ts
import { test, expect, chromium, BrowserContext } from "@playwright/test";
import { resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { startMockBackend, MockBackend } from "./mock_backend";

const HERE = resolve(fileURLToPath(import.meta.url), "..");
const EXT_PATH = resolve(HERE, "..", "..", "dist");
const FIXTURE = `file://${resolve(HERE, "fixture_pages", "john_3_es.html")}`;

let context: BrowserContext | null = null;
let backend: MockBackend | null = null;

test.beforeAll(async () => {
  backend = await startMockBackend(8765);
});

test.afterAll(async () => {
  await backend?.stop();
});

test.beforeEach(async () => {
  context = await chromium.launchPersistentContext("", {
    headless: false,
    args: [
      `--disable-extensions-except=${EXT_PATH}`,
      `--load-extension=${EXT_PATH}`,
      "--no-sandbox",
    ],
  });
});

test.afterEach(async () => {
  await context?.close();
  context = null;
});

test("injects 3 buttons per verse on a wol fixture page", async () => {
  // Spoof window.location.href via a navigation to the file:// fixture
  // and a content-script that interprets URL — for the test we override
  // the chapter context via a `<base>` tag set to a wol URL.
  const page = await context!.newPage();

  // The content_script reads window.location.hostname; for file:// URLs
  // the script's auto-boot is gated. We invoke `run()` manually via the
  // page after exposing it. In production, the script auto-runs on wol.
  await page.goto(FIXTURE);
  await page.addScriptTag({
    content: `
      // Simulate that we're on wol.jw.org/es/wol/b/r4/lp-s/nwt/E/2024/43/3
      // by patching window.location via a Proxy used by content_script.
      Object.defineProperty(window, '__JW_TEST_URL__', {
        value: 'https://wol.jw.org/es/wol/b/r4/lp-s/nwt/E/2024/43/3',
      });
    `,
  });
  // Note: the content_script auto-runs from the bundled extension only
  // when window.location.hostname === 'wol.jw.org'. For E2E we drive the
  // injector from the bundle directly via a small bridge.
  await page.waitForTimeout(500);

  const buttons = page.locator(".jw-ext-verse-actions");
  // Loose lower bound: 3 in the fixture
  await expect(buttons).toHaveCount(3);
});

test("clicking explain calls /api/v1/verse_markdown and shows tooltip", async () => {
  const page = await context!.newPage();
  await page.goto(FIXTURE);
  await page.waitForTimeout(500);

  await page.locator(`[data-verse='16'] .jw-ext-btn-explain`).click();
  await page.waitForTimeout(800);

  // Tooltip rendered
  await expect(page.locator(".jw-ext-tooltip")).toContainText("Juan 3:16");
  // Mock backend received the call
  const calls = backend!.requests.filter((r) => r.url === "/api/v1/verse_markdown");
  expect(calls.length).toBeGreaterThanOrEqual(1);
  expect((calls[0]!.body as any).reference).toBe("Juan 3:16");
});

test("clicking cross-refs renders link list", async () => {
  const page = await context!.newPage();
  await page.goto(FIXTURE);
  await page.waitForTimeout(500);

  await page.locator(`[data-verse='16'] .jw-ext-btn-crossrefs`).click();
  await page.waitForTimeout(800);

  await expect(page.locator(".jw-ext-tooltip a").first()).toBeVisible();
});

test("clicking save-vault without configured vault path shows error toast", async () => {
  const page = await context!.newPage();
  await page.goto(FIXTURE);
  await page.waitForTimeout(500);

  await page.locator(`[data-verse='1'] .jw-ext-btn-vault`).click();
  await page.waitForTimeout(500);

  await expect(page.locator(".jw-ext-toast-err")).toBeVisible();
});
```

> **Note for the implementer**: the test framework here uses a manual bootstrap because Playwright + file:// URLs do not trigger the content_script's hostname gate. Two strategies are acceptable: (a) use `addInitScript` to override `window.location` semantics, or (b) modify the auto-boot in `content_script.ts` to also accept a `__JW_TEST_URL__` global when the protocol is `file:` during E2E. Pick (b) and gate behind an `if (process.env.NODE_ENV === 'test' || hostname matches)`. Update `content_script.ts` accordingly before running these tests.

- [x] **Step 6: Patch content_script to honor `__JW_TEST_URL__`**

In `apps/wol-browser-extension/src/content_script.ts`, replace the auto-boot bottom block with:

```typescript
function _shouldBoot(): boolean {
  if (typeof window === "undefined") return false;
  if (window.location?.hostname === "wol.jw.org") return true;
  const override = (window as unknown as { __JW_TEST_URL__?: string }).__JW_TEST_URL__;
  return typeof override === "string" && override.startsWith("https://wol.jw.org/");
}

function _bootHref(): string {
  const override = (window as unknown as { __JW_TEST_URL__?: string }).__JW_TEST_URL__;
  return override ?? window.location.href;
}

if (_shouldBoot()) {
  if (document.readyState === "complete" || document.readyState === "interactive") {
    // Override location for buildReferenceFromUrl + detectLanguage.
    const ctx = buildReferenceFromUrl(_bootHref());
    if (ctx) run();
  } else {
    document.addEventListener("DOMContentLoaded", () => run());
  }
}
```

Also pass `_bootHref()` into `buildReferenceFromUrl` and `detectLanguage` inside `run()` (replace `window.location.href` references with a `getHref()` helper that returns the override when present).

- [x] **Step 7: Run E2E tests**

```bash
cd apps/wol-browser-extension
pnpm build
pnpm test:e2e
```
Expected: 4 passed.

- [x] **Step 8: Commit**

```bash
git add apps/wol-browser-extension/src/content_script.ts apps/wol-browser-extension/tests/playwright
git commit -m "test(wol-ext): playwright E2E with mocked WOL fixture + mocked localhost backend"
```

---

### Task 13: Privacy test — assert zero external requests

**Files:**
- Create: `apps/wol-browser-extension/tests/playwright/privacy.spec.ts`

This is the **bloqueante** test of Spec Risk #3. Anything reaching the network that isn't `localhost:8765` or `file://` or `wol.jw.org` is a hard fail.

- [x] **Step 1: Write the failing test**

```typescript
// apps/wol-browser-extension/tests/playwright/privacy.spec.ts
import { test, expect, chromium, BrowserContext } from "@playwright/test";
import { resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { startMockBackend, MockBackend } from "./mock_backend";

const HERE = resolve(fileURLToPath(import.meta.url), "..");
const EXT_PATH = resolve(HERE, "..", "..", "dist");
const FIXTURE = `file://${resolve(HERE, "fixture_pages", "john_3_en.html")}`;

const ALLOWED_PREFIXES = [
  "http://localhost:8765",
  "https://wol.jw.org",
  "file://",
  "chrome-extension://",
  "moz-extension://",
  "devtools://",
  "data:",
  "about:",
];

function isExternal(url: string): boolean {
  return !ALLOWED_PREFIXES.some((p) => url.startsWith(p));
}

let context: BrowserContext | null = null;
let backend: MockBackend | null = null;
const external: string[] = [];

test.beforeAll(async () => {
  backend = await startMockBackend(8765);
});

test.afterAll(async () => {
  await backend?.stop();
});

test.beforeEach(async () => {
  external.length = 0;
  context = await chromium.launchPersistentContext("", {
    headless: false,
    args: [
      `--disable-extensions-except=${EXT_PATH}`,
      `--load-extension=${EXT_PATH}`,
      "--no-sandbox",
    ],
  });
  context.on("request", (req) => {
    const u = req.url();
    if (isExternal(u)) external.push(u);
  });
});

test.afterEach(async () => {
  await context?.close();
  context = null;
});

test("zero external requests during full user flow", async () => {
  const page = await context!.newPage();
  await page.goto(FIXTURE);
  await page.waitForTimeout(400);

  // Drive the entire UI: open each action, type in popup.
  await page.locator(`[data-verse='1'] .jw-ext-btn-explain`).click();
  await page.waitForTimeout(400);
  await page.locator(`[data-verse='16'] .jw-ext-btn-crossrefs`).click();
  await page.waitForTimeout(400);

  // Brief settle to allow any background fetches to flush.
  await page.waitForTimeout(1_000);

  expect(external, `Saw external requests:\n${external.join("\n")}`).toEqual([]);
});

test("background health-check does not call anything but localhost", async () => {
  const page = await context!.newPage();
  await page.goto(FIXTURE);
  await page.waitForTimeout(2_000); // give background poll time

  const localhostCalls = backend!.requests.filter((r) => r.url === "/healthz");
  expect(localhostCalls.length).toBeGreaterThanOrEqual(1);
  expect(external).toEqual([]);
});
```

- [x] **Step 2: Run test**

Run: `pnpm test:privacy`
Expected: 2 passed. If FAIL: track the offending URL in `external[]` and remove the leak.

- [x] **Step 3: Add to CI as a blocking job**

Append to `.github/workflows/wol-extension.yml` (Task 14):

```yaml
- name: Privacy enforcement (BLOCKING)
  run: pnpm test:privacy
  working-directory: apps/wol-browser-extension
```

- [x] **Step 4: Commit**

```bash
git add apps/wol-browser-extension/tests/playwright/privacy.spec.ts
git commit -m "test(wol-ext): BLOCKING privacy test asserting zero non-localhost requests"
```

---

### Task 14: Package script (`pnpm package` → `.zip` for GitHub Releases)

**Files:**
- Create: `apps/wol-browser-extension/scripts/package.mjs`
- Create: `.github/workflows/wol-extension.yml`

- [x] **Step 1: Write the package script**

```javascript
// apps/wol-browser-extension/scripts/package.mjs
// Bundle the dist/ directory into dist-zip/jw-toolkit-wol-<version>.zip.
// Used by `pnpm package` locally and by the GitHub release workflow.

import { createReadStream, createWriteStream, existsSync, mkdirSync, readdirSync, readFileSync, statSync } from "node:fs";
import { join, relative, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { createGzip } from "node:zlib";
import archiver from "archiver";

const HERE = resolve(fileURLToPath(import.meta.url), "..", "..");
const DIST = join(HERE, "dist");
const OUT = join(HERE, "dist-zip");

if (!existsSync(DIST)) {
  console.error("dist/ not found — run `pnpm build` first.");
  process.exit(1);
}

const pkg = JSON.parse(readFileSync(join(HERE, "package.json"), "utf-8"));
const manifest = JSON.parse(readFileSync(join(DIST, "manifest.json"), "utf-8"));
const version = manifest.version ?? pkg.version ?? "0.0.0";
const zipName = `jw-toolkit-wol-${version}.zip`;
const zipPath = join(OUT, zipName);

mkdirSync(OUT, { recursive: true });

await new Promise((resolveP, rejectP) => {
  const output = createWriteStream(zipPath);
  const archive = archiver("zip", { zlib: { level: 9 } });
  output.on("close", () => {
    console.log(`Wrote ${zipPath} (${archive.pointer()} bytes)`);
    resolveP();
  });
  archive.on("error", rejectP);
  archive.pipe(output);
  archive.directory(DIST, false);
  archive.finalize();
});

// Hard upper bound — Spec metric: <500KB without optional deps, <800KB with.
const size = statSync(zipPath).size;
if (size > 800 * 1024) {
  console.error(`Bundle too large: ${size} bytes (>800KB). Investigate.`);
  process.exit(2);
}
```

Add `archiver` to `devDependencies`:

```bash
cd apps/wol-browser-extension
pnpm add -D archiver
```

- [x] **Step 2: Run package locally**

```bash
pnpm build
pnpm package
```
Expected: `dist-zip/jw-toolkit-wol-0.1.0.zip` created, size <800KB.

- [x] **Step 3: Write GitHub Releases workflow**

```yaml
# .github/workflows/wol-extension.yml
name: wol-browser-extension

on:
  push:
    branches: [main]
    paths:
      - "apps/wol-browser-extension/**"
      - "packages/jw-mcp/src/jw_mcp/rest_api.py"
      - ".github/workflows/wol-extension.yml"
  pull_request:
    paths:
      - "apps/wol-browser-extension/**"
  release:
    types: [published]

jobs:
  test-and-package:
    runs-on: ubuntu-latest
    defaults:
      run:
        working-directory: apps/wol-browser-extension
    steps:
      - uses: actions/checkout@v4
      - uses: pnpm/action-setup@v4
        with:
          version: 9
      - uses: actions/setup-node@v4
        with:
          node-version: "20"
          cache: pnpm
          cache-dependency-path: apps/wol-browser-extension/pnpm-lock.yaml

      - name: Install
        run: pnpm install --frozen-lockfile

      - name: Typecheck
        run: pnpm typecheck

      - name: Lint
        run: pnpm lint

      - name: Unit tests
        run: pnpm test

      - name: Install Playwright browsers
        run: pnpm exec playwright install --with-deps chromium

      - name: Build
        run: pnpm build

      - name: E2E tests
        run: pnpm test:e2e

      - name: Privacy enforcement (BLOCKING)
        run: pnpm test:privacy

      - name: Package
        run: pnpm package

      - name: Upload artifact
        uses: actions/upload-artifact@v4
        with:
          name: jw-toolkit-wol-zip
          path: apps/wol-browser-extension/dist-zip/*.zip
          if-no-files-found: error

  release:
    if: github.event_name == 'release'
    needs: test-and-package
    runs-on: ubuntu-latest
    steps:
      - uses: actions/download-artifact@v4
        with:
          name: jw-toolkit-wol-zip
          path: dist-zip
      - name: Attach to release
        uses: softprops/action-gh-release@v2
        with:
          files: dist-zip/*.zip
```

- [x] **Step 4: Commit**

```bash
git add apps/wol-browser-extension/scripts/package.mjs apps/wol-browser-extension/package.json .github/workflows/wol-extension.yml
git commit -m "feat(wol-ext): pnpm package script + CI workflow with release-zip attachment"
```

---

### Task 15: User-facing documentation

**Files:**
- Create: `docs/guias/wol-browser-ext.md`
- Modify: `docs/guias/README.md`
- Modify: `docs/VISION_AUDIT.md`
- Modify: `docs/ROADMAP.md`

- [x] **Step 1: Write the guide**

```markdown
# Guía: extensión WOL del JW Agent Toolkit

> Pieza de Fase 48. Spec: `docs/superpowers/specs/2026-05-31-fase-48-wol-browser-ext-design.md`.

Esta extensión añade 3 botones inline a cada versículo en `wol.jw.org`:

- 📖 **Explicar** — invoca `verse_explainer`.
- 🔗 **Referencias cruzadas** — devuelve hasta 8 cross-refs locales.
- 📝 **Guardar en Obsidian** — escribe un `.md` callout dentro de tu vault.

Todas las llamadas van **exclusivamente** a `http://localhost:8765`. Cero
telemetría. Cero analytics. Cero requests a servidores remotos.

## Requisitos

1. Toolkit instalado (`uv tool install jw-agent-toolkit` o clone + `uv sync`).
2. Servidor REST corriendo:

```bash
uv run uvicorn jw_mcp.rest_api:app --port 8765
```

3. Navegador soportado: Chrome 121+, Edge 121+, Firefox 121+.

## Instalación developer-mode (recomendada al inicio)

### Chrome / Edge

1. Descarga `jw-toolkit-wol-<version>.zip` de la última release.
2. Descomprime en un directorio estable.
3. Abre `chrome://extensions` y activa "Modo de desarrollador".
4. Haz clic en "Cargar descomprimida" y selecciona el directorio.

### Firefox

1. Descarga el `.zip`, renómbralo a `.xpi`.
2. Abre `about:debugging#/runtime/this-firefox`.
3. "Cargar complemento temporal…" → selecciona el `.xpi`.

> El complemento es temporal y se descarga al cerrar Firefox. Para
> instalación persistente, esperar a la publicación en AMO.

## Configuración

1. Haz clic en el icono de la extensión.
2. Pega la ruta absoluta de tu vault de Obsidian (debe contener `.obsidian/`).
3. Elige idioma (en/es/pt).
4. "Probar conexión" debe responder `Toolkit activo ✓`.

## Privacidad

- `host_permissions` está limitado a `http://localhost:8765/*` — el navegador
  bloquea automáticamente cualquier fetch fuera de ese origen.
- `tests/playwright/privacy.spec.ts` falla la CI si aparece una request a un
  host distinto.

## Troubleshooting

- **Badge gris "off"** — `jw mcp serve` no está corriendo.
- **`Error: vault_path is not inside an Obsidian vault`** — la ruta no
  contiene `.obsidian/`. Apunta a la raíz del vault, no a una subcarpeta
  externa.
- **Sin botones en la página** — la URL no coincide con el patrón
  `/[lang]/wol/b/r…/<book>/<chapter>`. Por ahora solo las páginas de capítulo
  bíblico tienen UI inline.
```

- [x] **Step 2: Add to the docs index and vision audit**

In `docs/guias/README.md`, add bullet:

```markdown
- [Extensión WOL](./wol-browser-ext.md) — botones inline en wol.jw.org (Fase 48).
```

In `docs/VISION_AUDIT.md`, add a row to the phases table (date 2026-05-31):

```markdown
| 48 | wol-browser-extension | done | apps/wol-browser-extension/ | 0 external requests, Playwright E2E green |
```

In `docs/ROADMAP.md`, mark Fase 48 as shipped with link to the guide.

- [x] **Step 3: Commit**

```bash
git add docs/guias/wol-browser-ext.md docs/guias/README.md docs/VISION_AUDIT.md docs/ROADMAP.md
git commit -m "docs(wol-ext): user guide + roadmap + vision audit"
```

---

### Task 16: Final verification + dist artifact sanity

**Files:** none (verification only)

- [x] **Step 1: Full local cycle**

```bash
cd apps/wol-browser-extension
pnpm install
pnpm typecheck
pnpm lint
pnpm test
pnpm build
pnpm test:e2e
pnpm test:privacy
pnpm package
ls -la dist-zip/
```
Expected: every command green; `dist-zip/jw-toolkit-wol-0.1.0.zip` <800KB.

- [x] **Step 2: Backend regression**

```bash
uv run pytest packages/jw-mcp -q
uv run pytest packages -q
```
Expected: full Python suite green, including the new CORS / cross-refs / vault-append tests, and no regression in the 1984 existing tests.

- [x] **Step 3: Manual smoke**

1. Run `uv run uvicorn jw_mcp.rest_api:app --port 8765`.
2. Load the unpacked extension into Chrome from `apps/wol-browser-extension/dist/`.
3. Configure vault path to a real Obsidian vault.
4. Navigate to `https://wol.jw.org/es/wol/b/r4/lp-s/nwt/E/2024/43/3`.
5. Verify 36 verses have 3 buttons each.
6. Click "Explicar" on John 3:16 → tooltip with markdown.
7. Click "Guardar a Obsidian" → file appears in `<vault>/Verses/Juan_3_16.md`.

- [x] **Step 4: Tag a candidate release**

```bash
git tag wol-ext/v0.1.0
git push origin wol-ext/v0.1.0
```

Then create a GitHub release pointing at the tag; the `release` job of the
workflow attaches the zip.

- [x] **Step 5: Commit (only if anything changed during verify)**

If verification revealed nothing to fix, no commit is needed. Otherwise:

```bash
git add -A
git commit -m "fix(wol-ext): polish discovered during full verification"
```

---

## Self-review

**Spec coverage checklist:**

- ✅ Manifest v3 with `host_permissions=["http://localhost:8765/*"]` and `content_scripts.matches=["https://wol.jw.org/*"]` — Task 1.
- ✅ `permissions=["storage"]` only — Task 1.
- ✅ `browser_specific_settings.gecko.id` for Firefox — Task 1.
- ✅ `JwApiClient` refuses non-localhost URLs (constructor + runtime guard) — Task 2.
- ✅ Verse detector with chapter context derived from URL — Task 3.
- ✅ Idempotent button injector + prefixed CSS — Task 4.
- ✅ i18n en/es/pt with fallback — Task 5.
- ✅ Content script auto-boots on `wol.jw.org` + test override hook — Task 6.
- ✅ Popup UI persisting vault path + language in `chrome.storage.local` — Task 7.
- ✅ CORS tightened from `["*"]` to explicit `wol.jw.org` + extension regex — Task 8.
- ✅ `POST /api/v1/cross_references` endpoint — Task 9.
- ✅ `POST /api/v1/vault/append` with `.obsidian/` marker + path-traversal defense — Task 10.
- ✅ ESLint + static test forbidding non-localhost URLs — Task 11.
- ✅ Playwright E2E with mocked WOL fixture + mocked backend — Task 12.
- ✅ Blocking privacy test (zero external requests) — Task 13.
- ✅ `pnpm package` → zip + GitHub Releases CI workflow — Task 14.
- ✅ User-facing docs + VISION_AUDIT row — Task 15.
- ✅ Final cross-verification + zip size guard — Task 16.

**Risk coverage:**

- Risk #1 (Web Store rejection) — distribution via dev-mode zip is the primary channel; CI does not depend on web stores.
- Risk #2 (WOL DOM drift) — `verse_detector.spec.ts` + fixture HTML; failures surface in unit test before E2E.
- Risk #3 (CORS `*`) — closed in Task 8.
- Risk #4 (toolkit not running) — `healthOrNull` returns `null`; popup status displays it.
- Risk #5 (publisher confusion) — addressed by docs (out of code scope).
- Risk #6 (FF API divergence) — manifest v3 used; no polyfill needed at 121+.
- Risk #7 (vaultPath = ~/.ssh) — closed in Task 10 with `.obsidian/` marker check + path-traversal guard.
- Risk #8 (service worker stale) — health-check runs on tab update events.

**Open questions for the implementer:**

1. The Playwright E2E uses `__JW_TEST_URL__` to bypass the hostname gate on `file://`. An alternative is to serve the fixture via a tiny static server on `https://wol.jw.org` with `--host-resolver-rules`; choose whichever is less brittle in CI.
2. The `cross_references` MVP delegates to the existing CDN search — verify the `filter_type="bibleVerse"` flag is supported by `CDNClient.search`; if not, fall back to `filter_type="all"` and post-filter by URL pattern.
3. Bundle size budget: the Spec says <500KB without Fase 47 dep, <800KB with. Task 14 enforces 800KB ceiling — tune if compression headroom is left.
4. Production submission to Chrome Web Store / AMO / Edge Add-ons is intentionally out of scope here; see Spec §"Distribución".

---

## Execution choice

This plan has 16 TDD tasks, mostly independent past Task 6 (content_script wiring). Recommended workflow:

- **Tasks 1–7** sequential — each builds the next layer of the extension code and unit tests; total ~3-4 hours of focused work.
- **Tasks 8–10** independent of each other and of 1–7 — backend changes. Can be parallelized to a second worker.
- **Tasks 11–13** depend on Tasks 1–10 being green — lint + Playwright. Sequential.
- **Tasks 14–16** depend on everything above.

For a single human worker: execute top-to-bottom. For subagent-driven development with `superpowers:subagent-driven-development`, dispatch a back-end agent on Tasks 8–10 in parallel with a front-end agent on Tasks 1–7 and rendez-vous before Task 12.

Resume points: any task can be re-run idempotently; tests guard against partial commits introducing regressions.
