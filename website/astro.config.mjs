import { defineConfig } from 'astro/config';
import mdx from '@astrojs/mdx';
import sitemap from '@astrojs/sitemap';
import tailwindcss from '@tailwindcss/vite';

// SITE_URL drives canonical URLs, sitemap, OG image absolute paths.
// On Vercel: set SITE_URL=https://<your-domain> in project env vars.
// Locally / fallback: uses the .vercel.app preview URL or the placeholder.
const site =
  process.env.SITE_URL ??
  (process.env.VERCEL_PROJECT_PRODUCTION_URL
    ? `https://${process.env.VERCEL_PROJECT_PRODUCTION_URL}`
    : process.env.VERCEL_URL
      ? `https://${process.env.VERCEL_URL}`
      : 'https://jw-agent-toolkit.vercel.app');

export default defineConfig({
  site,
  integrations: [mdx(), sitemap()],
  i18n: {
    defaultLocale: "es",
    locales: ["es", "en"],
    routing: {
      prefixDefaultLocale: false,
    },
  },
  // Backwards-compat redirects for URLs that never had a page file but were
  // linked from the homepage during earlier iterations. Astro emits native
  // 301 redirects in static output (Vercel honors them) and meta-refresh
  // pages in dev.
  redirects: {
    "/arquitectura": "/docs/architecture",
    "/en/arquitectura": "/en/docs/architecture",
    "/vision": "/docs/vision",
    "/en/vision": "/en/docs/vision",
  },
  vite: {
    plugins: [tailwindcss()],
  },
  markdown: {
    shikiConfig: {
      theme: 'github-dark-dimmed',
      wrap: true,
    },
  },
});
