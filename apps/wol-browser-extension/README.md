# wol-browser-extension

Manifest v3 extension for Chrome/Edge/Firefox that injects inline action buttons
into every `<span class="verse">` on `wol.jw.org`.

**Three actions per verse:**
- 📖 **Explain** — calls `POST /api/v1/verse_markdown` on the local toolkit and shows the rendered markdown in a tooltip.
- 🔗 **Cross-refs** — calls `POST /api/v1/cross_references` and renders a link list.
- 📝 **Save to Obsidian** — calls `POST /api/v1/vault/append` to drop a `.md` file in your vault.

**Privacy guarantee.** Every network call goes to `http://localhost:8765`.
The manifest's `host_permissions` allow-list and runtime guards in
`src/api.ts` make any other origin unreachable. A blocking Playwright test
(`tests/playwright/privacy.spec.ts`) fails CI if a non-localhost request
ever appears during a full user flow.

## Quickstart

```bash
pnpm install
pnpm test           # vitest unit tests
pnpm build          # outputs dist/
pnpm test:e2e       # playwright with mocked backend
pnpm test:privacy   # blocking — zero external requests
pnpm package        # → dist-zip/jw-toolkit-wol-<version>.zip
```

## Install (developer mode)

1. `pnpm build`
2. Chrome / Edge: `chrome://extensions` → enable Developer mode → "Load unpacked" → `dist/`.
3. Firefox: `about:debugging` → "This Firefox" → "Load Temporary Add-on" → pick `dist/manifest.json`.

## Local backend

The extension expects `jw-mcp` REST API on `http://localhost:8765`:

```bash
uv run uvicorn jw_mcp.rest_api:app --port 8765
```

Without the backend the extension renders buttons but every action surfaces a
"toolkit not running" toast instead of an error in the network tab.

See `docs/guias/wol-browser-ext.md` for full user-facing docs.
