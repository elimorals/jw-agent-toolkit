import { OGImageRoute } from "astro-og-canvas";
import { packages } from "../../data/packages";

/**
 * Dynamic Open Graph image generation.
 *
 * One PNG per "page key". BaseLayout computes the right key from the
 * current URL and emits <meta og:image="/og/{key}.png">. This is a
 * deliberate compromise: we don't generate a unique OG per docs page
 * (would inflate the build) — docs share /og/docs.png, packages have
 * their own /og/paquetes-{slug}.png, and the homepage has /og/home.png.
 */
const pageKeys: Record<string, { title: string; description?: string }> = {
  home: {
    title: "jw-agent-toolkit",
    description:
      "Toolkit técnico independiente · acceso programático a contenido público de jw.org",
  },
  docs: {
    title: "Documentación",
    description:
      "Conceptos · Guías · Referencia exhaustiva · Specs · 44 docs",
  },
  vision: {
    title: "Visión a largo plazo",
    description:
      "Hacia un ecosistema completo de IA local para Testigos de Jehová",
  },
  arquitectura: {
    title: "Arquitectura",
    description:
      "Capas estrictas · Citas verificables · Sin LLM en el camino crítico",
  },
};

// Add one entry per package
for (const p of packages) {
  pageKeys[`paquetes-${p.slug}`] = {
    title: p.name,
    description: `${p.tagline} — ${p.short.slice(0, 80)}`,
  };
}

export const { getStaticPaths, GET } = OGImageRoute({
  param: "slug",
  pages: pageKeys,
  getImageOptions: (_path, page) => ({
    title: page.title,
    description: page.description ?? "",
    bgGradient: [
      [11, 14, 19],
      [16, 22, 32],
    ],
    border: { color: [95, 199, 221], width: 14, side: "block-start" },
    padding: 80,
    font: {
      title: {
        color: [231, 236, 243],
        weight: "Medium",
        size: 88,
        lineHeight: 1.05,
        families: ["Fraunces"],
      },
      description: {
        color: [164, 175, 193],
        weight: "Normal",
        size: 34,
        lineHeight: 1.4,
        families: ["IBM Plex Sans"],
      },
    },
  }),
});
