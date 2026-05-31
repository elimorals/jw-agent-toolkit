# Fase 48 — `wol-browser-ext`: extensión Chrome/Firefox/Edge para wol.jw.org

> **Fecha**: 2026-05-31
> **Estado**: Diseño aprobado (pendiente de implementación)
> **Owner**: Elias
> **Tier**: 4 (nueva superficie JS)
> **Depende de**: Fase 20 (REST API en `localhost:8765`). **Opcional**: Fase 47 (TS port de `parse_reference`) para parsing sin red.
> **Documento padre**: [`2026-05-31-fases-39-48-overview.md`](2026-05-31-fases-39-48-overview.md)

## Motivación

El usuario JW promedio ya lee la Biblia en **wol.jw.org** desde su navegador. Hoy debe **abandonar la página** para usar el toolkit: copiar el versículo, abrir terminal, lanzar `jw verse_explainer`, pegar resultado en Obsidian. Cuatro pasos cuando la intención cabe en uno: "explícame este versículo y guárdalo".

Fase 48 cierra esa brecha con una **extensión de navegador** que inyecta UI inline en cada versículo de wol.jw.org. Tres acciones contextuales:

1. 📖 **Explicar** → llama a `verse_explainer` vía REST local.
2. 🔗 **Ver cross-refs** → llama a `get_cross_references` vía REST local.
3. 📝 **Guardar a Obsidian** → POST al adaptador de vault local de Fase 20.

Es la pieza más cercana al "donde ya está la gente" de todo el plan Fases 39-48: cero comandos, cero copy-paste, **resultado en la misma página que el usuario ya tenía abierta**.

## Objetivos (en orden de prioridad)

1. **UI inline en wol.jw.org** sin romper el layout existente ni meter telemetría.
2. **Zero-trust con backends remotos**: la extensión solo habla con `localhost:8765`. Nunca, bajo ninguna circunstancia, hace una request a un origen ≠ localhost.
3. **Funciona en Chrome, Edge, Firefox** con el **mismo manifest v3** (sin variantes por navegador salvo polyfill).
4. **Fallback gracioso** cuando el toolkit no está corriendo: botones disabled con tooltip explicativo.
5. **i18n nativo** (en/es/pt) desde el primer release.

## No-objetivos (boundaries vinculantes)

- **No** envía ningún dato a un servidor remoto. Sin analytics, sin Sentry, sin "telemetría anónima".
- **No** sustituye al MCP/CLI para flujos avanzados — esto es solo el "hot path" inline en wol.jw.org.
- **No** ataca otros sitios JW (jw.org, jw.org/finder, jw-broadcasting). Solo wol.jw.org. Otra extensión a futuro puede cubrirlos.
- **No** incluye un editor markdown propio para Obsidian: delega al adaptador REST (`POST /api/v1/vault/...`) de Fase 20.
- **No** distribuye contenido propio (Política #6 jw-gen). La extensión **reescribe** la página pero **no genera** contenido nuevo distribuible.

## Arquitectura

Nuevo workspace member `apps/wol-browser-extension/` (paquete **npm**, no Python). Sigue el mismo patrón de monorepo que `apps/obsidian-jw-bridge/`.

```
apps/wol-browser-extension/
├── manifest.json                      # v3, Chrome/Edge/Firefox compatible
├── package.json
├── tsconfig.json
├── vite.config.ts                     # bundler (vite + crxjs plugin)
├── src/
│   ├── content_script.ts              # corre en wol.jw.org/*, parsea DOM, inyecta botones
│   ├── background.ts                  # service worker: REST calls, health-check
│   ├── api.ts                         # wrapper fetch → http://localhost:8765/api/v1/*
│   ├── reference_parser.ts            # opcional: usa @jw-agent-toolkit/core (Fase 47) si presente
│   ├── dom/
│   │   ├── verse_detector.ts          # encuentra <span class="verse"> en wol DOM
│   │   ├── button_injector.ts         # crea los 3 botones por versículo
│   │   └── styles.css                 # CSS con prefijo .jw-ext-* para evitar colisión
│   ├── popup/                         # popup UI (settings)
│   │   ├── popup.html
│   │   ├── popup.ts
│   │   └── popup.css
│   ├── i18n/
│   │   ├── en.json
│   │   ├── es.json
│   │   └── pt.json
│   └── types.ts                       # tipos compartidos
├── icons/
│   ├── 16.png
│   ├── 48.png
│   └── 128.png
├── tests/
│   ├── playwright/                    # tests E2E contra wol.jw.org mock
│   │   ├── fixture_pages/             # HTML estático de wol capturado
│   │   └── extension.spec.ts
│   └── unit/                          # tests de api.ts, verse_detector, reference_parser
└── README.md
```

### Reglas duras de diseño

1. `manifest.json` declara **únicamente**:
   - `host_permissions: ["http://localhost:8765/*"]`
   - `content_scripts.matches: ["https://wol.jw.org/*"]`
   - **Cero permisos** como `tabs`, `webRequest`, `cookies`, `storage` global (solo `storage` mínimo para guardar vault path).
2. La extensión no usa **ningún** SDK de terceros (sin sentry-js, sin posthog-js, sin analytics).
3. CSS injectado lleva prefijo `.jw-ext-*` para no chocar con clases de wol.
4. `content_script` no modifica nodos existentes destructivamente: solo **anexa** botones tras detectar versículos.
5. Errores del backend local **nunca** se reportan a red; solo se loguean a `console.warn` con prefijo `[jw-ext]`.

## Manifest v3

```json
{
  "manifest_version": 3,
  "name": "JW Agent Toolkit — WOL Companion",
  "short_name": "JW Toolkit WOL",
  "version": "0.1.0",
  "description": "Inline explanations, cross-references, and Obsidian export for wol.jw.org. 100% local.",
  "icons": {
    "16": "icons/16.png",
    "48": "icons/48.png",
    "128": "icons/128.png"
  },
  "action": {
    "default_popup": "src/popup/popup.html",
    "default_icon": "icons/48.png"
  },
  "background": {
    "service_worker": "src/background.js",
    "type": "module"
  },
  "content_scripts": [
    {
      "matches": ["https://wol.jw.org/*"],
      "js": ["src/content_script.js"],
      "css": ["src/dom/styles.css"],
      "run_at": "document_idle"
    }
  ],
  "host_permissions": [
    "http://localhost:8765/*"
  ],
  "permissions": ["storage"],
  "browser_specific_settings": {
    "gecko": {
      "id": "jw-agent-toolkit@cipre.dev",
      "strict_min_version": "115.0"
    }
  }
}
```

`browser_specific_settings.gecko` es el único bloque firefox-only; Chrome y Edge lo ignoran. No usamos `webextension-polyfill` por defecto — manifest v3 APIs (`chrome.action`, `chrome.runtime`, `chrome.storage`) son cross-browser desde Firefox 121+.

## Flujo de usuario

### Setup inicial

1. Usuario instala el toolkit Python (`uv tool install jw-agent-toolkit` o repo clone).
2. Usuario corre `jw mcp serve` (lanza FastAPI en `localhost:8765`).
3. Usuario instala la extensión:
   - **Vía Web Store** (cuando se aprueba): un clic en `chrome.google.com/webstore`.
   - **Vía developer-mode** (recomendado al principio): descarga `.zip` desde `github.com/.../releases`, descomprime, "Load unpacked" en `chrome://extensions`.
4. Usuario abre el popup → introduce path del Obsidian vault (autocompletado vía `chrome.fileSystem` cuando es posible; manual cuando no).
5. La extensión hace `GET http://localhost:8765/healthz` al cargar la primera página de wol.jw.org. Si responde `{"status": "ok"}`: badge verde. Si no: badge gris + tooltip "Inicia el toolkit: `jw mcp serve`".

### Interacción inline

Cada vez que un usuario abre una página tipo `wol.jw.org/es/wol/b/r4/lp-s/nwt/E/2024/43/3` (Juan 3):

1. `content_script.ts` corre en `document_idle`.
2. `verse_detector.ts` busca todos los `<span class="verse">...</span>` (selector exacto que WOL usa, validado contra snapshot).
3. Por cada versículo, `button_injector.ts` anexa un `<div class="jw-ext-verse-actions">` con 3 botones SVG.
4. Click en 📖 → `api.explain({ reference, language }) → POST /api/v1/verse_markdown` (existente) o futuro `/api/v1/explain` específico → render como tooltip flotante junto al versículo.
5. Click en 🔗 → `api.crossRefs({ reference, language }) → POST /api/v1/cross_references` (nuevo endpoint a añadir en jw-mcp, ver "Cambios en REST API" abajo) → render lista en panel lateral colapsable.
6. Click en 📝 → `api.exportToVault({ reference, vaultPath, template: "callout" }) → POST /api/v1/vault/append` (nuevo endpoint) → toast confirmación "Guardado en `{vaultPath}/Versiculos/{ref}.md`".

## Reference parsing: opt-in a Fase 47

Sin Fase 47:
- Toda detección de referencia se delega al backend. `content_script` envía el **string crudo** (`"Juan 3:16"`) y el endpoint REST llama a `parse_reference` Python.
- Latencia: ~30-80ms por click (round-trip local).

Con Fase 47 instalado:
- La extensión detecta si `@jw-agent-toolkit/core` está disponible (publicado a npm y bundled como dep opcional).
- `reference_parser.ts` lo importa dinámicamente. Si el import falla, fallback a REST.
- Latencia: ~1ms (parse local). Solo la respuesta del agente sigue yendo por REST.

Esto se documenta como "optional optimization", no como requirement. El manifest no cambia.

## Cambios necesarios en el backend (jw-mcp)

Fase 48 requiere dos **nuevos endpoints** en `packages/jw-mcp/src/jw_mcp/rest_api.py`:

```python
@app.post("/api/v1/cross_references")
async def post_cross_references(req: CrossRefRequest) -> dict[str, Any]:
    """Return cross-refs panel for a verse reference."""
    ...

@app.post("/api/v1/vault/append")
async def post_vault_append(req: VaultAppendRequest) -> dict[str, Any]:
    """Append a verse-markdown block to a given file in the user's vault."""
    ...
```

Y un ajuste en CORS — actualmente `allow_origins=["*"]`. Eso técnicamente permite a wol.jw.org embebido, pero queremos ser **explícitos**:

```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://wol.jw.org", "chrome-extension://*", "moz-extension://*"],
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)
```

Validación: tests de la extensión envían `Origin: https://wol.jw.org` y verifican que la respuesta lleva `Access-Control-Allow-Origin` correcto.

> **Nota de compatibilidad**: el wildcard `chrome-extension://*` no es soportado por la spec CORS estándar — necesitamos resolverlo con una lista dinámica o middleware custom que valide el origen contra una regex. Implementación detallada en el plan hijo.

## Descubrimiento del Obsidian vault

Tres estrategias, en orden de preferencia:

1. **Si `obsidian-jw-bridge` (Fase 20 Obsidian plugin) está instalado y emparejado**: el plugin Obsidian expone su path vía la propia API REST (`GET /api/v1/obsidian/vault_info` — endpoint a añadir, devuelve el path del vault activo si Obsidian está corriendo y el plugin está activado).
2. **Manual via popup**: el usuario introduce el path absoluto. Persistido en `chrome.storage.local`.
3. **File System Access API** (Chrome only, requires user gesture): un botón "Seleccionar carpeta" que abre el picker nativo y guarda el `FileSystemDirectoryHandle`. Firefox no lo soporta; en Firefox solo está la opción 1 y 2.

El path nunca sale de la máquina del usuario. Se guarda en `chrome.storage.local`, no en `chrome.storage.sync`.

## Distribución y review process

Realidad operativa:

- **Chrome Web Store**: review puede tardar **2-8 semanas** la primera vez. Para extensiones con permisos amplios o que usan `host_permissions` con localhost, el reviewer puede pedir justificación adicional. **No es bloqueante para uso real**.
- **Firefox AMO**: review automatizado para self-distribution, manual para "Recommended". Tiempo ~3-7 días.
- **Edge Add-ons**: usa el mismo paquete que Chrome; review ~3-10 días.

**Estrategia de release**:

1. **v0.1 (developer-mode-only)**: publicado como `.zip` en GitHub Releases. El README explica cómo cargarlo en modo developer en cada navegador. Este es el **canal principal** durante las primeras semanas.
2. **v0.2+ (web stores)**: una vez la API es estable y tenemos golden tests verdes, se sube a Chrome Web Store + Firefox AMO + Edge en paralelo.
3. **Documentación**: `docs/guias/wol-browser-ext.md` explica los 3 caminos con screenshots.

Esta decisión es deliberada: forzar a la primera ola de usuarios por developer-mode evita que un rechazo del store nos bloquee el ciclo de iteración.

## Privacidad y compliance

**Privacy guarantee** (textual en el README y en la página del store):

> Esta extensión **no** envía datos a ningún servidor remoto. Todas las requests van exclusivamente a `http://localhost:8765`, que es el servidor local del toolkit corriendo en tu propia máquina. Sin analytics. Sin telemetría. Sin Sentry. Sin Google Analytics. El código es 100% open source bajo MIT.

**Cómo se enforza técnicamente**:

- `manifest.host_permissions` solo lista `localhost:8765`. El navegador **bloquea** automáticamente cualquier `fetch()` a otro origen.
- CI corre `eslint-plugin-no-restricted-syntax` con regla `fetch(...)` solo permitida si la URL es `localhost:8765` literal o `${API_BASE}` donde `API_BASE === "http://localhost:8765"`.
- `tests/unit/no_external_calls.spec.ts` parsea todo el bundle compilado y falla si encuentra URLs `http(s)://[^l]`.

**Chrome Web Store privacy disclosure**: marcado "Does not collect user data" + descripción detallada del scope.

## Estrategia de tests

### Tests unitarios

- `api.ts`: mock `fetch`, verifica que solo se invoca con `localhost:8765`. Verifica handling de network errors, JSON malformado, status ≠ 2xx.
- `reference_parser.ts`: 30+ casos golden compartidos con Python (mismo fixture JSON que Fase 47).
- `verse_detector.ts`: usa snapshot HTML real de wol.jw.org (commited en `tests/playwright/fixture_pages/`).

### Tests E2E (Playwright)

```typescript
// tests/playwright/extension.spec.ts
test("inyecta botones en cada versículo y llama a REST local", async ({ context }) => {
  // 1. Carga la extensión desde disk
  const extensionPath = path.resolve(__dirname, "../../dist");
  const browser = await chromium.launchPersistentContext("", {
    headless: false,
    args: [`--disable-extensions-except=${extensionPath}`, `--load-extension=${extensionPath}`],
  });

  // 2. Mock del REST API local en :8765 con MSW o tinyhttp
  await startMockBackend(8765);

  // 3. Navega a fixture HTML que replica wol.jw.org/es/wol/b/.../43/3
  const page = await browser.newPage();
  await page.goto("file://" + fixturePath("john_3_es.html"));

  // 4. Verifica que aparecen botones en cada verso
  const buttons = await page.locator(".jw-ext-verse-actions").count();
  expect(buttons).toBeGreaterThanOrEqual(36); // John 3 has 36 verses

  // 5. Click en "Explicar" para verso 16, verifica que el mock recibió la request
  await page.locator("[data-verse='16'] .jw-ext-explain").click();
  await expect(page.locator(".jw-ext-tooltip")).toContainText("amó tanto al mundo");
});
```

Tests corren en CI sobre Chrome (headless) y Firefox (via Playwright firefox channel). Edge usa el mismo binary que Chrome.

### Tests de privacidad (bloqueante en CI)

```typescript
test("nunca llama a un origen ≠ localhost:8765", async ({ page }) => {
  const externalRequests: string[] = [];
  page.on("request", req => {
    const url = req.url();
    if (!url.startsWith("http://localhost:8765") && !url.startsWith("file://") && !url.startsWith("https://wol.jw.org")) {
      externalRequests.push(url);
    }
  });
  // ... interact with extension ...
  expect(externalRequests).toEqual([]);
});
```

## Integración con el ecosistema

| Pieza | Relación |
|---|---|
| **Fase 20** (Obsidian bridge) | La extensión llama a los endpoints `vault/*` ya existentes. |
| **Fase 39** (NLI runtime) | Si está activo, la explicación devuelta lleva `nli_score`. La extensión lo muestra como badge verde/amarillo. |
| **Fase 40** (provenance) | El tooltip de explicación muestra `accessed_at` y un link "Re-validar" que dispara `provenance_check`. |
| **Fase 47** (TS port) | Optional dependency para parsing client-side. |
| **CLI `jw`** | El popup tiene un link "¿Toolkit no corre? Ejecuta `jw mcp serve` en una terminal". |

## Riesgos y mitigaciones

| # | Riesgo | Mitigación |
|---|---|---|
| 1 | Chrome Web Store rechaza por `host_permissions` con localhost | Distribución developer-mode primaria. Web Store es secundario, no bloqueante. |
| 2 | WOL cambia su estructura DOM, los selectores rompen | Tests E2E con snapshots HTML que detectan el drift. Fase 22-style snapshot refresh semanal. |
| 3 | CORS configurado para `*` actualmente permite que cualquier sitio explote el backend local | Tightening del CORS a wol.jw.org + `chrome-extension://*` regex. Documentado como cambio breaking en jw-mcp v0.2. |
| 4 | Usuario instala extensión sin tener el toolkit corriendo | Health-check + badge gris + tooltip con instrucciones claras. Popup tiene un botón "Test conexión". |
| 5 | Múltiples extensiones de terceros similares confunden al usuario | Documentar que esta es la oficial; verificar publisher en Web Store. |
| 6 | Firefox WebExtensions API diverge de Chrome en algún punto | Usar polyfill `webextension-polyfill` solo si aparece divergencia. Por ahora manifest v3 es suficiente. |
| 7 | El usuario edita el `vaultPath` y apunta a un directorio sensitivo (ej. `~/.ssh`) | `POST /api/v1/vault/append` valida que el path esté dentro de un Obsidian vault detectado (presencia de `.obsidian/`). Si no, devuelve 400. |
| 8 | Service worker se duerme y el health-check stale | Health-check en cada navigation a wol.jw.org, no en service worker. |

## Métricas de éxito de la fase

- ✅ Extensión carga en Chrome, Edge, Firefox desde `.zip` developer-mode sin errores en consola.
- ✅ Sobre `wol.jw.org/es/wol/b/r4/lp-s/nwt/E/2024/43/3`, aparecen 3 botones por cada uno de los 36 versículos de Juan 3.
- ✅ Click en "Explicar" devuelve respuesta del agente local en <2s en hardware típico.
- ✅ Click en "Guardar a Obsidian" crea archivo `.md` en el vault con el bloque correcto.
- ✅ Test de privacidad pasa: 0 requests a origen ≠ localhost.
- ✅ i18n funciona en en/es/pt (detectado vía `navigator.language` o configurado en popup).
- ✅ Sin toolkit corriendo: badge gris + tooltip + ninguna request falla con uncaught exception.
- ✅ `dist/` bundleado pesa <500KB (sin Fase 47 dep) o <800KB (con Fase 47).

## Pendientes explícitos (post-Fase 48)

- **Soporte para jw.org/finder** (mismo patrón, dominio distinto). Fase futura.
- **Dashboard de uso local** (cuántas explicaciones por día, etc.). Solo cuando esté Fase 43 (tracing) maduro.
- **Sync de bookmarks JW Library ↔ extensión**. Fase futura, depende de M11.
- **Mobile**: las extensiones no son soportadas en Safari iOS ni Chrome Android para webstore. Esto queda fuera de scope; mobile va por la PWA / nativo de Fase 47 cuando exista.

## Cómo verificar al cerrar

```bash
# 1. Backend
uv run uvicorn jw_mcp.rest_api:app --port 8765

# 2. Bundle de la extensión
cd apps/wol-browser-extension
pnpm install
pnpm build              # produce dist/

# 3. Tests unitarios
pnpm test

# 4. Tests E2E (Playwright + Chrome + Firefox)
pnpm test:e2e

# 5. Test de privacidad explícito
pnpm test:privacy       # falla si hay cualquier request a origen ≠ localhost

# 6. Bundle del .zip distribuible
pnpm package            # produce dist-zip/jw-toolkit-wol-0.1.0.zip
```

## Plan de implementación (alto nivel)

Spec hijo: `docs/superpowers/plans/2026-05-31-fase-48-wol-browser-ext-plan.md` (a escribir tras aprobar este spec).

Pasos cronológicos:

1. Scaffold del workspace member npm (`apps/wol-browser-extension/package.json` + `manifest.json` + vite config).
2. `content_script.ts` + `verse_detector.ts` + selectores validados contra snapshot HTML.
3. `api.ts` + `background.ts` con health-check.
4. Tightening CORS en `packages/jw-mcp/src/jw_mcp/rest_api.py` + nuevos endpoints `/cross_references` y `/vault/append`.
5. `button_injector.ts` + CSS prefijado.
6. Popup UI + i18n (en/es/pt).
7. Tests unitarios + E2E con Playwright.
8. Test de privacidad bloqueante.
9. Bundle + script `pnpm package` que produce `.zip`.
10. Documentación: `docs/guias/wol-browser-ext.md` con screenshots para Chrome/Edge/Firefox developer-mode.
11. (Opcional) Submission a Chrome Web Store / Firefox AMO / Edge Add-ons.
12. Audit 1:1 en `docs/VISION_AUDIT.md`.

Cada paso con su PR + tests + sin regresiones en los 1984 tests Python existentes.
