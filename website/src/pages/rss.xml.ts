/**
 * RSS 2.0 feed for the docs collection.
 *
 * AI crawlers (Perplexity, ChatGPT, Claude) and feed readers use this to
 * discover new pages without re-crawling the full sitemap. We emit the
 * top-level docs (excluding superpowers specs/plans which are very long
 * and not meant for casual feed consumption).
 */

import rss from "@astrojs/rss";
import type { APIContext } from "astro";
import { getCollection } from "astro:content";

const EXCLUDED_PREFIXES = ["superpowers/", "cookbook/_common"];

/**
 * Fallback when a doc has no `date` frontmatter. F47 baseline date —
 * older guides predate the per-entry `date` schema. Newer guides
 * (F49+) carry an explicit `date` so RSS readers rank them as fresh.
 */
const FALLBACK_DATE = new Date("2026-06-01T00:00:00.000Z");

function titleFromId(id: string): string {
  const tail = id.split("/").slice(1).join("/") || id;
  return tail.replace(/[-_]/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
}

function parseDate(raw: string | undefined): Date {
  if (!raw) return FALLBACK_DATE;
  const parsed = new Date(raw);
  return Number.isNaN(parsed.valueOf()) ? FALLBACK_DATE : parsed;
}

export async function GET(context: APIContext): Promise<Response> {
  const docs = await getCollection("docs");
  const items = docs
    .filter(
      (entry) => !EXCLUDED_PREFIXES.some((prefix) => entry.id.startsWith(prefix)),
    )
    .map((entry) => ({
      title: entry.data.title ?? titleFromId(entry.id),
      description: entry.data.description ?? "",
      link: `/docs/${entry.id}`,
      pubDate: parseDate(entry.data.date),
    }))
    .sort((a, b) => b.pubDate.getTime() - a.pubDate.getTime());

  return rss({
    title: "jw-agent-toolkit · Novedades",
    description:
      "Updates, guides, and specs for the jw-agent-toolkit project — Python monorepo, MCP server, RAG, agents, fine-tuning, browser extension.",
    site: context.site ?? "https://jw-agent-toolkit.vercel.app/",
    items,
    customData:
      "<language>es</language>" +
      "<copyright>GPL-3.0</copyright>" +
      "<docs>https://www.rssboard.org/rss-specification</docs>",
  });
}
