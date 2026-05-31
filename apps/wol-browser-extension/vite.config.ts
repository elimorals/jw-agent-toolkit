import { crx } from "@crxjs/vite-plugin";
import { defineConfig } from "vite";

import manifest from "./manifest.json" with { type: "json" };

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
