# jw-agent-toolkit Desktop (Tauri)

Cross-platform desktop wrapper around the REST API (`jw_mcp.rest_api`).
Single-window webview pointing at `http://127.0.0.1:8765/dashboard`,
with the toolkit running as a child process.

## Status

Scaffolding only — wired so `cargo tauri dev` (after `npm install` in
`/apps/desktop`) launches a window and brings up the Python backend.
Not yet packaged for distribution.

## Layout

```
apps/desktop/
├── package.json          ← Node frontend stub (Vite + plain JS)
├── src/
│   └── main.js           ← Frontend entry — just delegates to the iframe
├── tauri.conf.json       ← Tauri config
├── src-tauri/
│   ├── Cargo.toml
│   ├── tauri.conf.json   ← Per-target overrides
│   └── src/
│       └── main.rs       ← Spawns the Python REST API and opens the window
└── README.md
```

## How to run (developer)

```
# 1. Start the Python REST API in another terminal
uv pip install fastapi uvicorn
.venv/bin/uvicorn jw_mcp.rest_api:app --port 8765

# 2. Launch Tauri (requires Rust + Node)
cd apps/desktop
npm install
cargo tauri dev
```

## Build a binary

```
cargo tauri build
# Outputs:
#   target/release/jw-toolkit-desktop  (macOS .app inside)
```

## Notes

- The Python backend is bundled as a child process for development. In
  production builds you'll want to embed a portable Python (e.g. via
  PyInstaller) and bind it via `tauri-plugin-shell`.
- The window points at `localhost:8765` — the user can also hit
  `/dashboard`, `/api/v1/verse`, etc.
