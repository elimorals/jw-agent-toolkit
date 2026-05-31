// Bundle the dist/ directory into dist-zip/jw-toolkit-wol-<version>.zip.
// Used by `pnpm package` locally and by the GitHub release workflow.

import archiver from "archiver";
import {
  createWriteStream,
  existsSync,
  mkdirSync,
  readFileSync,
  statSync,
} from "node:fs";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const HERE = resolve(dirname(fileURLToPath(import.meta.url)), "..");
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
    resolveP(undefined);
  });
  archive.on("error", rejectP);
  archive.pipe(output);
  archive.directory(DIST, false);
  archive.finalize();
});

// Hard upper bound — Spec metric: <500KB without optional deps, <800KB with.
const size = statSync(zipPath).size;
const ceiling = 800 * 1024;
if (size > ceiling) {
  console.error(`Bundle too large: ${size} bytes (>${ceiling}). Investigate.`);
  process.exit(2);
}
