/**
 * llms-full.txt — expanded variant of llms.txt that ships the actual
 * Markdown body of every doc inline so an LLM with no browsing capability
 * can ingest the whole site in a single fetch.
 *
 * Pages are emitted in a stable order, each prefixed with an H1 of its
 * title and a `Source:` line that links back to the canonical web URL.
 */

import type { APIContext } from "astro";
import { getCollection } from "astro:content";

const TYPE = "text/plain; charset=utf-8";

interface Doc {
  id: string;
  title: string;
  description: string;
  body: string;
}

function titleFromId(id: string): string {
  const tail = id.split("/").slice(1).join("/") || id;
  return tail.replace(/[-_]/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
}

// Lightweight "strip Markdown front-matter and image binary noise" pass.
function cleanBody(body: string): string {
  // The collection's body should already be without YAML front-matter, but
  // we strip just in case a `---` block leaks in.
  let s = body.trim();
  if (s.startsWith("---")) {
    const end = s.indexOf("\n---", 3);
    if (end !== -1) s = s.slice(end + 4).trim();
  }
  return s;
}

export async function GET({ site }: APIContext): Promise<Response> {
  const origin = (site ?? new URL("https://jw-agent-toolkit.vercel.app/"))
    .origin;

  const entries = await getCollection("docs");
  const docs: Doc[] = entries
    .map((entry) => ({
      id: entry.id,
      title: entry.data.title ?? titleFromId(entry.id),
      description: entry.data.description ?? "",
      body: (entry as unknown as { body?: string }).body ?? "",
    }))
    .sort((a, b) => a.id.localeCompare(b.id));

  const out: string[] = [];
  out.push("# jw-agent-toolkit — full corpus");
  out.push("");
  out.push(
    "Generated dump of every public documentation page for LLMs that cannot fetch URLs at inference time. The short, curated map is at " +
      origin +
      "/llms.txt.",
  );
  out.push("");
  out.push("Source repository: https://github.com/elimorals/jw-agent-toolkit");
  out.push("Canonical site: " + origin + "/");
  out.push("");
  out.push("---");
  out.push("");

  for (const doc of docs) {
    const url = `${origin}/docs/${doc.id}`;
    out.push(`# ${doc.title}`);
    out.push("");
    if (doc.description) {
      out.push(`> ${doc.description}`);
      out.push("");
    }
    out.push(`Source: ${url}`);
    out.push("");
    out.push(cleanBody(doc.body));
    out.push("");
    out.push("---");
    out.push("");
  }

  return new Response(out.join("\n"), {
    headers: { "Content-Type": TYPE },
  });
}
