# Obsidian — JW Agent Toolkit Bridge

Native Obsidian plugin that drives the local `jw-agent-toolkit` REST API.

## What it does

- **Linkify** Bible references in markdown (selection / current note / whole vault) → `[Juan 3:16](jwlibrary:///finder?bible=43003016&wtlocale=S)`. Recognises 17 locales (en, es, pt-PT, fr, de, it, ja, ko, ru, cs, hr, da, nl, fi, tl, vi, bem).
- **Convert legacy `jwpub://`** links in any note to the modern `jwlibrary://` form.
- **Insert verse** at cursor: fetches verse text from wol.jw.org and renders it as a link, blockquote, or Obsidian `[!quote]` callout.
- **Sync JW Library backup**: drops one `.md` per user note (with frontmatter) under `<vault>/JW Library/`.
- **Index this vault into the toolkit RAG store**: lets the agent reason about your notes alongside the JW corpus.

## Prerequisites

Run the toolkit REST API somewhere reachable from the Obsidian host:

```bash
cd /path/to/jw-agent-toolkit
uv pip install fastapi uvicorn
uv run uvicorn jw_mcp.rest_api:app --host 127.0.0.1 --port 8765
```

In the plugin settings, point **Toolkit REST API URL** to that address.

## Build

```bash
cd apps/obsidian-jw-bridge
pnpm install
pnpm run build   # writes main.js next to manifest.json
```

Copy `main.js`, `manifest.json`, and (if present) `styles.css` to your vault under `.obsidian/plugins/jw-agent-toolkit-bridge/` and enable it from **Community Plugins → Installed**.

## Commands

| Command | Default hotkey | What it does |
|---|---|---|
| Linkify selection | — | Replace selected text with linkified version. |
| Linkify current note | — | Rewrites the active `.md` in-place. |
| Linkify entire vault | — | Walks every `.md` and updates the ones that change. |
| Convert jwpub:// links in current note | — | Refresh legacy notes. |
| Insert Bible verse at cursor… | — | Modal prompt → fetch + insert. |
| Export JW Library backup into vault… | — | Modal: path to `.jwlibrary`. Writes notes as `.md`. |
| Index this vault into the toolkit RAG store | — | Triggers incremental vault → RAG. |
| Check bridge health | — | Pings `/healthz`. |

Auto-linkify on save is opt-in under settings (debounced 800 ms).

## Settings

- **Toolkit REST API URL** (default `http://localhost:8765`).
- **Default language** (ISO). Drives the rendered labels.
- **wtlocale override** (JW code). Force a specific URL locale.
- **Book-name length**: `short` / `medium` / `long`.
- **Verse template**: `plain` / `link` / `blockquote` / `callout` / `callout-collapsed`.
- **Include verse text in insert**: fetch the verse body or just the reference link.
- **Auto-linkify on save**: experimental; runs after every `.md` modification.

## How it talks to the toolkit

Everything goes through HTTP `POST`s to the FastAPI endpoints documented in `packages/jw-mcp/src/jw_mcp/rest_api.py`:

- `POST /api/v1/linkify`
- `POST /api/v1/convert_links`
- `POST /api/v1/verse_markdown`
- `POST /api/v1/vault/index`
- `POST /api/v1/vault/export`
- `GET /healthz`

No state is kept on the Obsidian side; the toolkit owns the RAG store and sidecar state files under `~/.jw-agent-toolkit/`.

## Licence

GPL-3.0-only, same as the rest of the monorepo.
