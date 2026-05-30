import { defineCollection, z } from "astro:content";
import { glob } from "astro/loaders";

/**
 * Docs collection: pulls every .md file from the repo's /docs directory.
 * The site is at /website and the docs live at /docs (sibling), so we
 * point the glob loader at ../docs.
 *
 * Slugs preserve the docs directory structure:
 *   docs/ARCHITECTURE.md           → /docs/architecture
 *   docs/conceptos/glosario.md     → /docs/conceptos/glosario
 *   docs/guias/fine-tuning-local.md → /docs/guias/fine-tuning-local
 */
const docs = defineCollection({
  loader: glob({
    pattern: "**/*.md",
    base: "../docs",
    generateId: ({ entry }) => entry.replace(/\.md$/, "").toLowerCase(),
  }),
  schema: z.object({
    title: z.string().optional(),
    description: z.string().optional(),
  }),
});

export const collections = { docs };
