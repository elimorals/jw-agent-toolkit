/**
 * llms.txt — emerging standard (Jeremy Howard, sept. 2024) for LLM-friendly
 * site discovery. Renders as plain Markdown with a top-level title, a short
 * project summary, and grouped section headings whose bullets are
 * `[title](url): one-line description` links into the docs.
 *
 * Spec reference: https://llmstxt.org/
 *
 * This route is server-side at build time; Astro emits a static `llms.txt`
 * to `dist/` so the public URL is `/llms.txt`.
 */

import type { APIContext } from "astro";
import { getCollection } from "astro:content";

const TYPE = "text/plain; charset=utf-8";

interface DocLine {
  id: string;
  title: string;
  description: string;
  topDir: string;
}

const SECTION_LABEL: Record<string, string> = {
  conceptos: "Conceptos",
  guias: "Guías",
  referencia: "Referencia",
  superpowers: "Specs y planes",
  cookbook: "Cookbook ejecutable",
  "plugin-sdk": "Plugin SDK",
};

const SECTION_ORDER = [
  "guias",
  "conceptos",
  "referencia",
  "cookbook",
  "plugin-sdk",
  "superpowers",
];

function titleFromId(id: string): string {
  const tail = id.split("/").slice(1).join("/") || id;
  return tail
    .replace(/[-_]/g, " ")
    .replace(/\b\w/g, (c) => c.toUpperCase());
}

export async function GET({ site }: APIContext): Promise<Response> {
  const docs = await getCollection("docs");
  const origin = (site ?? new URL("https://jw-agent-toolkit.vercel.app/")).origin;

  const lines: DocLine[] = docs
    .map((entry) => {
      const topDir = entry.id.split("/")[0] ?? "";
      return {
        id: entry.id,
        title: entry.data.title ?? titleFromId(entry.id),
        description: entry.data.description ?? "",
        topDir,
      };
    })
    // Skip translated mirrors (English variants live under top-level dirs too,
    // but locale-specific copies are not duplicated here).
    .sort((a, b) => a.id.localeCompare(b.id));

  const grouped = new Map<string, DocLine[]>();
  for (const line of lines) {
    const list = grouped.get(line.topDir) ?? [];
    list.push(line);
    grouped.set(line.topDir, list);
  }

  const orderedSections = [
    ...SECTION_ORDER.filter((k) => grouped.has(k)),
    ...[...grouped.keys()]
      .filter((k) => !SECTION_ORDER.includes(k))
      .sort(),
  ];

  const out: string[] = [];
  out.push("# jw-agent-toolkit");
  out.push("");
  out.push(
    "> Toolkit técnico independiente para acceso programático a contenido público de jw.org. Monorepo Python (CLI, MCP, RAG, agentes, fine-tuning local) con extensión de navegador y bridge de Obsidian. Todas las citas son verificables y la síntesis con LLM es opcional, nunca en el camino crítico.",
  );
  out.push("");
  out.push(
    "Este archivo es un mapa curado del sitio para asistentes basados en modelos de lenguaje (estándar [llmstxt.org](https://llmstxt.org/)). La versión expandida con el contenido inline está en [/llms-full.txt](" +
      origin +
      "/llms-full.txt).",
  );
  out.push("");
  out.push("- Idiomas: español (default) e inglés.");
  out.push("- Site: " + origin + "/");
  out.push("- Sitemap: " + origin + "/sitemap-index.xml");
  out.push("- RSS: " + origin + "/rss.xml");
  out.push("- Código: https://github.com/elimorals/jw-agent-toolkit");
  out.push("");

  for (const section of orderedSections) {
    const list = grouped.get(section) ?? [];
    if (list.length === 0) continue;
    out.push(`## ${SECTION_LABEL[section] ?? titleFromId(section)}`);
    out.push("");
    for (const line of list) {
      const url = `${origin}/docs/${line.id}`;
      const desc = line.description ? `: ${line.description}` : "";
      out.push(`- [${line.title}](${url})${desc}`);
    }
    out.push("");
  }

  out.push("## Paquetes del monorepo");
  out.push("");
  out.push(
    "- [jw-core](" +
      origin +
      "/paquetes/jw-core): clientes HTTP, parsers, resolver de citas, cache.",
  );
  out.push(
    "- [jw-cli](" +
      origin +
      "/paquetes/jw-cli): CLI Typer sobre el toolkit completo.",
  );
  out.push(
    "- [jw-mcp](" +
      origin +
      "/paquetes/jw-mcp): servidor MCP para Claude Desktop y cualquier cliente MCP.",
  );
  out.push(
    "- [jw-rag](" + origin + "/paquetes/jw-rag): índice y búsqueda híbrida.",
  );
  out.push(
    "- [jw-agents](" +
      origin +
      "/paquetes/jw-agents): agentes procedurales (apologetics, verse_explainer, research_topic, etc.).",
  );
  out.push(
    "- [jw-eval](" + origin + "/paquetes/jw-eval): evaluación offline contra golden cases.",
  );
  out.push(
    "- [jw-gen](" +
      origin +
      "/paquetes/jw-gen): generación con safety + policy gates.",
  );
  out.push(
    "- [jw-finetune](" +
      origin +
      "/paquetes/jw-finetune): pipeline local de fine-tuning con Unsloth.",
  );
  out.push("");

  return new Response(out.join("\n"), {
    headers: { "Content-Type": TYPE },
  });
}
