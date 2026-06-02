import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { fileURLToPath } from "node:url";

import { BrowserContext, chromium, expect, test } from "@playwright/test";

import { MockBackend, startMockBackend } from "./mock_backend";

const HERE = resolve(fileURLToPath(import.meta.url), "..");
const EXT_PATH = resolve(HERE, "..", "..", "dist");
const FIXTURE_HTML = readFileSync(
  resolve(HERE, "fixture_pages", "john_3_en.html"),
  "utf-8",
);
const WOL_URL = "https://wol.jw.org/en/wol/b/r1/lp-e/nwt/E/2024/43/3";

/** Any URL whose prefix is in this list is considered safe. Everything else
 * is a hard test failure. The list is intentionally narrow: the extension
 * must NEVER touch a non-localhost origin. */
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
      "--disable-features=PrivateNetworkAccessRespectPreflightResults,BlockInsecurePrivateNetworkRequests",
    ],
  });
  context.on("request", (req) => {
    const u = req.url();
    if (isExternal(u)) external.push(u);
  });
  // Same trick as extension.spec.ts: route wol.jw.org to the fixture so
  // manifest matches activates the content_script.
  await context.route("https://wol.jw.org/**", async (route) => {
    if (route.request().resourceType() === "document") {
      await route.fulfill({
        status: 200,
        contentType: "text/html",
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
  // See extension.spec.ts for why this warm-up is required (Chrome MV3 PNA).
  await page.evaluate(() => fetch("http://localhost:8765/healthz")).catch(() => {});
  await page.waitForTimeout(800);
}

test("zero external requests during full user flow", async () => {
  const page = await context!.newPage();
  await bootWolPage(page);

  await page.locator(`[data-verse='1'] .jw-ext-btn-explain`).click();
  await page.waitForTimeout(400);
  await page.locator(`[data-verse='16'] .jw-ext-btn-crossrefs`).click();
  await page.waitForTimeout(400);

  // Brief settle to allow any background fetches to flush.
  await page.waitForTimeout(1_000);

  expect(
    external,
    `Saw external requests:\n${external.join("\n")}`,
  ).toEqual([]);
});

test("background health-check does not call anything but localhost", async () => {
  const page = await context!.newPage();
  await bootWolPage(page);
  await page.waitForTimeout(2_000); // give background poll time

  const localhostCalls = backend!.requests.filter((r) => r.url === "/healthz");
  expect(localhostCalls.length).toBeGreaterThanOrEqual(1);
  expect(external).toEqual([]);
});
