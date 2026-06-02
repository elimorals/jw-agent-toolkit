import { defineConfig } from "tsup";

export default defineConfig({
  entry: ["src/index.ts", "src/books.ts", "src/versification.ts"],
  format: ["esm", "cjs"],
  dts: true,
  splitting: false,
  sourcemap: true,
  clean: true,
  target: "es2022",
  treeshake: true,
});
