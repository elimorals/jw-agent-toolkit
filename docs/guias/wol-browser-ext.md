# Guía: extensión WOL del JW Agent Toolkit

> Pieza de **Fase 48**. Spec: `docs/superpowers/specs/2026-05-31-fase-48-wol-browser-ext-design.md`.
> Plan: `docs/superpowers/plans/2026-05-31-fase-48-wol-browser-ext-plan.md`.
> Código: [`apps/wol-browser-extension/`](../../apps/wol-browser-extension/).

Esta extensión añade 3 botones inline a cada versículo en `wol.jw.org`:

- **📖 Explicar** — invoca `verse_explainer` y muestra el markdown en un tooltip.
- **🔗 Referencias cruzadas** — devuelve hasta 8 cross-refs locales.
- **📝 Guardar en Obsidian** — escribe un `.md` callout dentro de tu vault.

Todas las llamadas van **exclusivamente** a `http://localhost:8765`. Cero
telemetría. Cero analytics. Cero requests a servidores remotos.

## Requisitos

1. Toolkit instalado (`uv tool install jw-agent-toolkit` o clone + `uv sync`).
2. Servidor REST corriendo:

   ```bash
   uv run uvicorn jw_mcp.rest_api:app --port 8765
   ```

3. Navegador soportado: Chrome 121+, Edge 121+, Firefox 121+.

## Instalación (developer mode)

### Chrome / Edge

1. Descarga `jw-toolkit-wol-<version>.zip` de la última release (o ejecuta `pnpm package` localmente, ver "Build").
2. Descomprime en un directorio estable.
3. Abre `chrome://extensions` y activa "Modo de desarrollador".
4. Haz clic en "Cargar descomprimida" y selecciona el directorio descomprimido.

### Firefox

1. Descarga el `.zip`, renómbralo a `.xpi`.
2. Abre `about:debugging#/runtime/this-firefox`.
3. "Cargar complemento temporal…" → selecciona el `.xpi`.

> El complemento es temporal y se descarga al cerrar Firefox. Para
> instalación persistente, esperar a la publicación en AMO (fuera del scope
> de Fase 48).

## Configuración

1. Haz clic en el icono de la extensión.
2. Pega la ruta absoluta de tu vault de Obsidian (debe contener `.obsidian/`).
3. Elige idioma (en/es/pt).
4. "Probar conexión" debe responder `Toolkit activo ✓`.

## Garantías de privacidad (lo que NO hace)

La extensión no puede, técnicamente, llamar a ningún host distinto de
`localhost:8765`. Hay **3 capas de defensa**:

1. **Manifest v3**: `host_permissions=["http://localhost:8765/*"]`. El navegador
   bloquea cualquier `fetch` fuera de ese origen *antes* de salir del proceso.
2. **Runtime guard**: `JwApiClient.assertLocal()` arroja error si el URL no
   empieza con `http://localhost:8765/`. Es defensa-en-profundidad por si el
   manifest cambia.
3. **CI bloqueante**: `tests/playwright/privacy.spec.ts` registra cada `request`
   del browser context durante un flujo completo de usuario. **Cualquier URL
   externa rompe la build**.

Además:
- ESLint flat config prohíbe `fetch()` directos fuera de `src/api.ts` y URL
  literales no-localhost en todo `src/`.
- El backend (`packages/jw-mcp/src/jw_mcp/rest_api.py`) tiene CORS limitado a
  `https://wol.jw.org` y `(chrome|moz)-extension://` — un sitio malicioso
  abierto en otra pestaña no podría llamar tu toolkit local aunque adivine la
  IP.

## Seguridad del endpoint `vault/append`

El endpoint **rechaza con HTTP 400** si:

- `vault_path` no existe o no es un directorio.
- `vault_path` ni ninguno de sus ancestros contiene una carpeta `.obsidian/`.
- `subdir` resuelve fuera del vault tras seguir `..` y symlinks.
- `vault_path` es `/`, `~`, o cadena vacía.

Esto cierra **Spec Risk #7**: aunque un atacante consiga acceso al popup,
no puede apuntar el `vault_path` a `~/.ssh` o `/etc` y sobrescribir.

## Build local

```bash
cd apps/wol-browser-extension
pnpm install
pnpm test           # 34 vitest unit tests
pnpm typecheck      # tsc --noEmit
pnpm lint           # eslint flat config
pnpm build          # outputs dist/ (~20KB raw, ~8KB gzip)
pnpm test:e2e       # Playwright (requiere `pnpm exec playwright install chromium`)
pnpm test:privacy   # BLOCKING — zero external requests
pnpm package        # → dist-zip/jw-toolkit-wol-<version>.zip
```

## Endpoints REST consumidos

| Método | Endpoint | Botón |
|---|---|---|
| GET | `/healthz` | Background poll + popup "Probar conexión" |
| POST | `/api/v1/verse_markdown` | 📖 Explicar |
| POST | `/api/v1/cross_references` | 🔗 Referencias cruzadas |
| POST | `/api/v1/vault/append` | 📝 Guardar en Obsidian |

## Troubleshooting

| Síntoma | Diagnóstico | Fix |
|---|---|---|
| Badge gris "off" | `jw mcp serve` no está corriendo | `uv run uvicorn jw_mcp.rest_api:app --port 8765` |
| `Error: vault_path is not inside an Obsidian vault` | la ruta no contiene `.obsidian/` | apunta a la raíz del vault, no a una subcarpeta externa |
| Sin botones en la página | URL no coincide con el patrón `/lang/wol/b/...` | Solo las páginas de capítulo bíblico tienen UI inline por ahora |
| Error CORS en consola | navegador caché viejo con CORS `*` | recarga la extensión en `chrome://extensions` tras el upgrade backend |
| Toast `vault path not configured` | no guardaste el path en el popup | abre popup → pega ruta → "Guardar" |

## Estructura del código

```
apps/wol-browser-extension/
├── manifest.json           # MV3, host_permissions=localhost:8765 only
├── eslint.config.js        # flat config; bans fetch outside api.ts + non-localhost URLs
├── src/
│   ├── api.ts              # JwApiClient — única superficie con fetch
│   ├── background.ts       # service worker: health poll + badge
│   ├── content_script.ts   # wires detector→injector→handlers
│   ├── config.ts           # API_BASE literal
│   ├── types.ts            # request/response shapes
│   ├── dom/
│   │   ├── verse_detector.ts   # span.verse[data-verse] iteration
│   │   ├── button_injector.ts  # idempotent action buttons
│   │   ├── tooltip.ts          # XSS-safe (no innerHTML with arbitrary strings)
│   │   └── styles.css          # .jw-ext-* prefixed
│   ├── i18n/{en,es,pt}.json
│   └── popup/popup.{html,ts,css}
└── tests/
    ├── unit/               # vitest (34 tests)
    └── playwright/         # E2E + privacy.spec.ts (BLOCKING)
```

## Métricas

| Métrica | Valor |
|---|---|
| Unit tests | 34 verde |
| Bundle (raw) | ~20 KB |
| Bundle (gzip) | ~8 KB |
| Zip de release | 13 KB |
| Ceiling pactado | 800 KB |
| Externos detectados por privacy.spec | 0 |
