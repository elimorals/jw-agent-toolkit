# jw-agent-toolkit · sitio web

Sitio estático construido con **Astro 5 + Tailwind 4 + MDX**. Lee directamente los `.md` del directorio `../docs/` del monorepo y los renderiza como páginas navegables.

## Desarrollo

```bash
cd website
npm install            # primera vez
npm run dev            # arranca en http://localhost:4321
```

## Build & preview

```bash
npm run build          # genera dist/
npm run preview        # sirve dist/ localmente
```

## Estructura

```
website/
├── src/
│   ├── components/        # DisclaimerBar, Header, Footer, PackageCard, RecommendedCard
│   ├── layouts/           # BaseLayout, DocsLayout
│   ├── pages/
│   │   ├── index.astro    # Landing principal
│   │   └── docs/
│   │       ├── index.astro          # Índice de toda la documentación
│   │       └── [...slug].astro      # Catchall que renderiza cualquier docs/**/*.md
│   ├── styles/global.css  # Design tokens (Tailwind @theme) + prose styles
│   └── content.config.ts  # Content collection que apunta a ../docs/
├── public/                # favicon, og-image, etc.
├── astro.config.mjs
├── tailwind.config.mjs    # (Tailwind 4 usa @theme en CSS — config mínimo)
└── package.json
```

## Filosofía de diseño

El sitio está **inspirado** en la sensibilidad visual sobria de jw.org (dark theme, layout denso en cards) **pero con identidad propia**:

- Sin replicar el logo "JW.ORG" ni la tipografía institucional
- Accent cyan-teal (`#5fc7dd`) en lugar del azul navy de jw.org
- Tipografía: **Fraunces** (display serif variable) + **IBM Plex Sans** (body) + **JetBrains Mono** (código)
- Disclaimer persistente en el top como diseño, no como disculpa enterrada en footer

Todo el branding deja claro que es un **proyecto técnico independiente**, no afiliado a Watch Tower Bible and Tract Society ni a Jehovah's Witnesses.

## Añadir contenido

Para añadir documentación: crea o edita un `.md` en `../docs/`. El sitio lo descubre automáticamente vía el `glob` loader de Astro 5 y genera la ruta `/docs/{path-without-extension}` en lowercase.

Para cambiar páginas custom (landing, índice de docs): edita los `.astro` en `src/pages/`.

## Deploy

El sitio es **estático puro** (no SSR, no edge functions). El build incluye:

1. `astro build` → 52 páginas HTML estáticas en `dist/`
2. `pagefind --site dist --output-subdir pagefind` → índice de búsqueda en `dist/pagefind/`
3. `astro-og-canvas` → 10 OG images PNG en `dist/og/` (al renderizar el endpoint)

### Vercel (recomendado)

Este sitio vive en `/website` dentro de un monorepo. Para que Vercel lo detecte:

1. **Import repo** en Vercel → selecciona `elimorals/jw-agent-toolkit`
2. **Root Directory**: `website` (¡importante!)
3. Framework Preset: `Astro` (auto-detectado)
4. Build Command: `npm run build` (heredado del `vercel.json`)
5. Output Directory: `dist`
6. (Opcional) **Environment Variables**:
   - `SITE_URL=https://tu-dominio.com` — para canonical URLs y OG image absolutas. Si no la pones, usa automáticamente `VERCEL_PROJECT_PRODUCTION_URL`.

El `vercel.json` incluido define cache headers para `/pagefind/*`, `/og/*` y `/_astro/*`.

Tiempo de build esperado: ~1m 15s (astro 2s + pagefind 1s + npm install ~70s + canvaskit-wasm ~12MB download la primera vez).

### Otros hosts

Funciona sin ajustes en:

- **Netlify**: build command `npm run build`, publish directory `website/dist`, base directory `website`
- **Cloudflare Pages**: build command `npm run build`, build output `dist`, root directory `/website`
- **GitHub Pages**: push del `dist/` a la rama `gh-pages` (manual o via GitHub Action)
- Cualquier static host: sirve `dist/` tal cual

## Licencia

GPL-3.0-only, igual que el resto del monorepo.
