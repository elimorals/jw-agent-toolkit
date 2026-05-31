import { resolve } from "node:path";
import { fileURLToPath } from "node:url";

import { BrowserContext, chromium, expect, test } from "@playwright/test";

import { MockBackend, startMockBackend } from "./mock_backend";

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

/**
 * The content_script auto-boots only when ``window.location.hostname ===
 * 'wol.jw.org'`` OR ``window.__JW_TEST_URL__`` points at wol.jw.org. We use
 * the latter (set via ``addInitScript`` BEFORE the page loads) for file://
 * fixtures.
 */
async function bootWolPage(page: import("@playwright/test").Page) {
  await page.addInitScript(() => {
    (window as unknown as { __JW_TEST_URL__: string }).__JW_TEST_URL__ =
      "https://wol.jw.org/es/wol/b/r4/lp-s/nwt/E/2024/43/3";
  });
  await page.goto(FIXTURE);
  await page.waitForTimeout(800);
}

test("injects 3 buttons per verse on a wol fixture page", async () => {
  const page = await context!.newPage();
  await bootWolPage(page);
  const wraps = page.locator(".jw-ext-verse-actions");
  await expect(wraps).toHaveCount(4); // john_3_es.html has 4 verses
});

test("clicking explain calls /api/v1/verse_markdown and shows tooltip", async () => {
  const page = await context!.newPage();
  await bootWolPage(page);

  await page.locator(`[data-verse='16'] .jw-ext-btn-explain`).click();
  await page.waitForTimeout(800);

  await expect(page.locator(".jw-ext-tooltip")).toContainText("Juan 3:16");
  const calls =
    backend!.requests.filter((r) => r.url === "/api/v1/verse_markdown");
  expect(calls.length).toBeGreaterThanOrEqual(1);
  expect((calls[0]!.body as { reference: string }).reference).toBe("Juan 3:16");
});

test("clicking cross-refs renders link list", async () => {
  const page = await context!.newPage();
  await bootWolPage(page);

  await page.locator(`[data-verse='16'] .jw-ext-btn-crossrefs`).click();
  await page.waitForTimeout(800);

  await expect(page.locator(".jw-ext-tooltip a").first()).toBeVisible();
});

test("clicking save-vault without configured vault path shows error toast", async () => {
  const page = await context!.newPage();
  await bootWolPage(page);

  await page.locator(`[data-verse='1'] .jw-ext-btn-vault`).click();
  await page.waitForTimeout(500);

  await expect(page.locator(".jw-ext-toast-err")).toBeVisible();
});
