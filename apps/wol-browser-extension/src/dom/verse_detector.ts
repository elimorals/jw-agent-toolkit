import { displayName, type Language } from "@jw-agent-toolkit/core";

import type { VerseTarget } from "../types";

export interface ChapterContext {
  /** Localized book name as printed in the URL slug. */
  book: string;
  chapter: number;
}

/**
 * Map a WOL URL language segment to the language code recognized by
 * `@jw-agent-toolkit/core`. The package today supports en/es/pt; everything
 * else falls back to English so the UI still gets a recognizable label.
 */
function normalizeLang(lang: string): Language {
  const lower = lang.toLowerCase();
  if (lower.startsWith("es")) return "es";
  if (lower.startsWith("pt")) return "pt";
  return "en";
}

/**
 * Parse a canonical WOL bible URL of the form
 *   https://wol.jw.org/<lang>/wol/b/<rev>/<edition>/<pub>/<bookNum>/<chapter>
 */
export function buildReferenceFromUrl(href: string): ChapterContext | null {
  let url: URL;
  try {
    url = new URL(href);
  } catch {
    return null;
  }
  if (url.hostname !== "wol.jw.org") return null;
  // WOL bible URLs are deeply segmented and the depth varies between
  // editions: e.g. /es/wol/b/r4/lp-s/nwt/E/2024/43/3 has SIX segments
  // between `r<rev>` and `<book>/<chap>`. We anchor on the `/wol/b/` prefix
  // (canonical bible flag) and the two trailing numeric segments.
  const m = url.pathname.match(
    /^\/(?<lang>[a-z]{1,3})\/wol\/b\/.+\/(?<book>\d{1,2})\/(?<chap>\d{1,3})$/i,
  );
  if (!m?.groups) return null;
  const bookGroup = m.groups["book"];
  const chapGroup = m.groups["chap"];
  const langGroup = m.groups["lang"];
  if (!bookGroup || !chapGroup || !langGroup) return null;
  const bookNum = Number(bookGroup);
  const chapter = Number(chapGroup);
  if (!Number.isFinite(bookNum) || bookNum < 1 || bookNum > 66) return null;
  if (!Number.isFinite(chapter) || chapter < 1) return null;
  const lang = normalizeLang(langGroup);
  // The package's `displayName` covers all 66 books in en/es/pt, replacing
  // the four hardcoded names that used to live here. If the language is
  // unsupported it returns the English form; if the book number is out of
  // range we already bailed above so the `?? ` fallback is only defense
  // against a future package downgrade.
  const book = displayName(bookNum, lang) ?? `[book ${bookNum}]`;
  return { book, chapter };
}

// Real WOL DOM (verified against wol.jw.org/es/wol/b/r4/lp-s/nwtsty/43/3):
//
//   <span id="v43-3-16-1" class="v">
//     <a class="vl vx vp study">16 </a>
//     Porque Dios amó tanto al mundo...
//   </span>
//
// The verse number lives inside the leading anchor and ALSO in the parent
// span's id as ``v{book}-{chap}-{verse}-{idx}``. We use the id because it's
// the most stable channel — anchor text formatting changes across pubs.
const VERSE_ID_RE = /^v(\d+)-(\d+)-(\d+)-\d+$/;

export function detectVerses(
  doc: Document,
  ctx: ChapterContext | null,
): VerseTarget[] {
  if (!ctx) return [];
  const out: VerseTarget[] = [];
  // The selector deliberately accepts both the real WOL DOM (span.v with id)
  // and the legacy fixture DOM (span.verse with data-verse) so unit tests
  // don't need to know about WOL internals.
  for (const node of doc.querySelectorAll<HTMLElement>("span.v, span.verse")) {
    const verseNum = extractVerseNum(node);
    if (verseNum === null) continue;
    out.push({
      verseNum,
      reference: `${ctx.book} ${ctx.chapter}:${verseNum}`,
      node,
    });
  }
  return out;
}

function extractVerseNum(node: HTMLElement): number | null {
  // Real WOL: id matches v{book}-{chap}-{verse}-{idx}.
  const id = node.id;
  if (id) {
    const m = id.match(VERSE_ID_RE);
    if (m && m[3]) {
      const n = Number(m[3]);
      if (Number.isFinite(n) && n > 0) return n;
    }
  }
  // Legacy fixture / test DOM: data-verse attribute.
  const attr = node.getAttribute("data-verse");
  if (attr) {
    const n = Number(attr);
    if (Number.isFinite(n) && n > 0) return n;
  }
  return null;
}
