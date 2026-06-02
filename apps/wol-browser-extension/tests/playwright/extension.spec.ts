import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { fileURLToPath } from "node:url";

import { BrowserContext, chromium, expect, test } from "@playwright/test";

import { MockBackend, startMockBackend } from "./mock_backend";

const HERE = resolve(fileURLToPath(import.meta.url), "..");
const EXT_PATH = resolve(HERE, "..", "..", "dist");
const FIXTURE_HTML = readFileSync(
  resolve(HERE, "fixture_pages", "john_3_es.html"),
  "utf-8",
);
const WOL_URL = "https://wol.jw.org/es/wol/b/r4/lp-s/nwt/E/2024/43/3";

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
      // The fixture page is served under https://wol.jw.org so the content
      // script gets injected. Fetches from there to http://localhost:8765
      // trip Chrome's Private Network Access check. Real users bypass this
      // via the localhost exception; in headless test runs we have to opt
      // out explicitly.
      "--disable-features=PrivateNetworkAccessRespectPreflightResults,BlockInsecurePrivateNetworkRequests",
    ],
  });
  // Serve the fixture under the real wol.jw.org URL so content_scripts.matches
  // fires and the extension is actually injected. Sub-resources are aborted
  // to keep the test hermetic — no real network leaves the box.
  await context.route("https://wol.jw.org/**", async (route) => {
    if (route.request().resourceType() === "document") {
      await route.fulfill({
        status: 200,
        contentType: "text/html",
        headers: {
          // Mirror what wol.jw.org would let through plus what the content
          // script needs: connect-src must include the local API base, or
          // every fetch the extension makes is silently dropped.
          "Content-Security-Policy":
            "default-src 'self' https: data:; script-src 'self' 'unsafe-inline'; connect-src 'self' http://localhost:8765",
        },
        body: FIXTURE_HTML,
      });
    } else {
      await route.abort();
    }
  });
});

test.afterEach(async () => {
  await context?.close();
  context = null;
});

async function bootWolPage(page: import("@playwright/test").Page) {
  await page.goto(WOL_URL);
  // Chrome MV3 Private Network Access requires the page-origin to make at
  // least one successful fetch to the private network before fetches from
  // the isolated content-script world are permitted. The extension's
  // background poller does this in real usage; in tests we warm it
  // explicitly so click handlers don't race the first /healthz.
  await page.evaluate(() => fetch("http://localhost:8765/healthz")).catch(() => {});
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
