# Cookbook — copy-pasteable recipes

> 12 short recipes for common jw-agent-toolkit tasks. Every recipe is a Markdown file with executable Python blocks tested by `pytest-cookbook` in CI.

## Scope reminder

These recipes target **publications of Jehovah's Witnesses** — wol.jw.org, JWPUB, EPUBs from the organization, Watchtower / Awake! / study books, etc.

## How to read a recipe

Each `.md` file follows the same structure:

1. **¿Qué construyes?** — one-line description of the output.
2. **Código (copy-pasteable)** — one or more ` ```python ` blocks. Blocks marked `# test` on their first line are executed by CI.
3. **Por qué funciona** — short explanation of the key decisions.
4. **Variaciones** — alternative tweaks.
5. **Próximo paso** — link to a related recipe.

## Markers

- `# test` — always run in CI.
- `# test slow` — only run with `pytest -m slow` (skipped by default).
- `# test skip-until-fase=N` — skipped with a reason until that Fase ships.

## Index

| # | Slug | Tema |
|---|---|---|
| 01 | `resolve-bible-reference` | Parsear "Juan 3:16" → `BibleRef` |
| 02 | `search-and-synthesize` | Buscar tema vía `CDNClient` (mockeado) |
| 03 | `telegram-bot` | Stub de bot conectado al REST API local |
| 04 | `finetune-llama-3` | Pipeline jw-finetune (slow) |
| 05 | `add-parser` | Plugin parser para formato custom |
| 06 | `custom-embedder` | Plugin embedder con vectores numpy |
| 07 | `add-nli` | Wrap agente con fidelity NLI (F39) |
| 08 | `publish-to-pypi` | Setup de release con trusted publishing |
| 09 | `trace-agent-run` | Tracing local (espera F43) |
| 10 | `calibrate-golden-case` | YAML golden + `jw eval` (F22) |
| 11 | `browser-extension` | WOL browser extension (F48) |
| 12 | `capacitor-app` | Capacitor mobile (espera F47) |
