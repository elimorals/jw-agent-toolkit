import { BibleRef, displayName, langFromWolPath } from "@jw-agent-toolkit/core";

import type { VerseTarget } from "../types";

export interface ChapterContext {
  /** Localized book name as printed in the URL slug. */
  book: string;
  chapter: number;
}

/**
 * Parse a canonical WOL bible URL into a localized chapter context.
 *
 * F56.5: delegates URL parsing to `BibleRef.fromWolUrl` + `langFromWolPath`
 * from `@jw-agent-toolkit/core`. The extension is now just a thin adapter
 * from `BibleRef` to the `ChapterContext` shape its UI expects.
 */
export function buildReferenceFromUrl(href: string): ChapterContext | null {
  const ref = BibleRef.fromWolUrl(href);
  if (ref == null) return null;
  const lang = langFromWolPath(href) ?? "en";
  const book = displayName(ref.bookNum, lang) ?? `[book ${ref.bookNum}]`;
  return { book, chapter: ref.chapter };
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
