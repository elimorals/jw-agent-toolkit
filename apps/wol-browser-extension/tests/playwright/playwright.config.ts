import { defineConfig } from "@playwright/test";

export default defineConfig({
  testDir: ".",
  timeout: 30_000,
  fullyParallel: false, // extension launch holds a unique user-data-dir
  workers: 1, // each spec starts a mock backend on :8765 — must run serially
  reporter: [["list"]],
  use: {
    // Chrome MV3 extensions need a non-headless context in Playwright.
    headless: false,
    viewport: { width: 1280, height: 800 },
  },
  projects: [
    {
      name: "chromium-with-extension",
      use: { browserName: "chromium" },
    },
  ],
});
