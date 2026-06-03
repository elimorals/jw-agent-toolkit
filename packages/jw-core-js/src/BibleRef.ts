/**
 * BibleRef — structured representation of a parsed Bible reference.
 *
 * The shape mirrors `jw_core.models.BibleRef` so JSON payloads round-trip
 * cleanly between the Python backend and any JS client.
 */

import { canonicalName } from "./books.js";
import type { Language } from "./books.js";
import { getLanguageConfig } from "./languages.js";

export interface BibleRefInput {
  bookNum: number;
  bookCanonical: string;
  chapter: number;
  verseStart?: number | null;
  verseEnd?: number | null;
  detectedLanguage: Language;
  rawMatch: string;
}

export class BibleRef {
  readonly bookNum: number;
  readonly bookCanonical: string;
  readonly chapter: number;
  readonly verseStart: number | null;
  readonly verseEnd: number | null;
  readonly detectedLanguage: Language;
  readonly rawMatch: string;

  constructor(init: BibleRefInput) {
    if (init.bookNum < 1 || init.bookNum > 66) {
      throw new RangeError(`bookNum out of range: ${init.bookNum}`);
    }
    if (init.chapter < 1) {
      throw new RangeError(`chapter must be >= 1: ${init.chapter}`);
    }
    if (init.verseStart != null && init.verseStart < 1) {
      throw new RangeError(`verseStart must be >= 1: ${init.verseStart}`);
    }
    if (init.verseEnd != null && init.verseEnd < 1) {
      throw new RangeError(`verseEnd must be >= 1: ${init.verseEnd}`);
    }
    this.bookNum = init.bookNum;
    this.bookCanonical = init.bookCanonical;
    this.chapter = init.chapter;
    this.verseStart = init.verseStart ?? null;
    this.verseEnd = init.verseEnd ?? null;
    this.detectedLanguage = init.detectedLanguage;
    this.rawMatch = init.rawMatch;
  }

  get hasVerse(): boolean {
    return this.verseStart != null;
  }

  get verseRange(): string {
    if (this.verseStart == null) return "";
    if (this.verseEnd != null && this.verseEnd !== this.verseStart) {
      return `${this.verseStart}-${this.verseEnd}`;
    }
    return String(this.verseStart);
  }

  /** Render as "Book chapter:verse[-end]" using the canonical English name. */
  display(): string {
    const name = canonicalName(this.bookNum) ?? this.bookCanonical;
    let out = `${name} ${this.chapter}`;
    if (this.verseStart != null) out += `:${this.verseRange}`;
    return out;
  }

  /**
   * Build the canonical wol.jw.org URL for this reference.
   *
   * Pattern:
   *   https://wol.jw.org/{iso}/wol/b/{wol_resource}/{lp_tag}/{pub}/{book}/{chapter}
   *
   * When `verseStart` is set, the WOL `#study=discover&v=BB:CC:VV` anchor
   * is appended. `pub` defaults to the language's preferred Bible.
   */
  wolUrl(lang: Language = "en", pub?: string): string {
    const cfg = getLanguageConfig(lang);
    const publication = pub ?? cfg.defaultBible;
    let url = `https://wol.jw.org/${cfg.iso}/wol/b/${cfg.wolResource}/${cfg.lpTag}/${publication}/${this.bookNum}/${this.chapter}`;
    if (this.verseStart != null) {
      url += `#study=discover&v=${this.bookNum}:${this.chapter}:${this.verseStart}`;
    }
    return url;
  }

  /** Plain-object form, suitable for JSON.stringify and IPC. */
  toJSON(): BibleRefInput {
    return {
      bookNum: this.bookNum,
      bookCanonical: this.bookCanonical,
      chapter: this.chapter,
      verseStart: this.verseStart,
      verseEnd: this.verseEnd,
      detectedLanguage: this.detectedLanguage,
      rawMatch: this.rawMatch,
    };
  }

  /**
   * Inverse of `wolUrl()`: parse a canonical WOL bible URL back into a
   * `BibleRef`. Returns `null` for non-WOL URLs or unrecognized shapes.
   * F56.5.
   *
   * Accepts both chapter-level and verse-level URLs:
   *   https://wol.jw.org/es/wol/b/r4/lp-s/nwtsty/43/3
   *   https://wol.jw.org/es/wol/b/r4/lp-s/nwtsty/43/3#study=discover&v=43:3:16
   *
   * The path segments between `/wol/b/` and the trailing `<book>/<chapter>`
   * vary across editions; we only constrain the prefix and the two trailing
   * numeric segments. The verse is read from the optional `#v=B:C:V` anchor.
   */
  static fromWolUrl(href: string): BibleRef | null {
    let url: URL;
    try {
      url = new URL(href);
    } catch {
      return null;
    }
    if (url.hostname !== "wol.jw.org") return null;
    const m = url.pathname.match(
      /^\/(?<lang>[a-z]{1,3})\/wol\/b\/.+\/(?<book>\d{1,2})\/(?<chap>\d{1,3})$/i,
    );
    if (!m?.groups) return null;
    const bookStr = m.groups["book"];
    const chapStr = m.groups["chap"];
    const langSeg = m.groups["lang"];
    if (!bookStr || !chapStr || !langSeg) return null;
    const bookNum = Number(bookStr);
    const chapter = Number(chapStr);
    if (!Number.isFinite(bookNum) || bookNum < 1 || bookNum > 66) return null;
    if (!Number.isFinite(chapter) || chapter < 1) return null;

    // Optional verse from #v=BB:CC:VV anchor.
    let verseStart: number | null = null;
    const fragMatch = url.hash.match(/v=(\d+):(\d+):(\d+)/);
    if (fragMatch && fragMatch[3]) {
      const v = Number(fragMatch[3]);
      if (Number.isFinite(v) && v > 0) verseStart = v;
    }

    const lang = langFromWolPath(href) ?? "en";
    const canonical = canonicalName(bookNum) ?? `Book${bookNum}`;
    return new BibleRef({
      bookNum,
      bookCanonical: canonical,
      chapter,
      verseStart,
      verseEnd: null,
      detectedLanguage: lang,
      rawMatch: href,
    });
  }
}

/**
 * Map a WOL URL or URL language segment to a supported `Language`.
 * WOL uses `/e/`, `/s/`, `/t/` segments and ISO-639-1 codes (`en`, `es`,
 * `pt-BR`). We accept either a full URL or a bare segment ("pt-BR",
 * "es", "/t/wol/..."). Returns `null` when the language is not one of
 * the three the package supports. F56.5.
 */
export function langFromWolPath(input: string): Language | null {
  if (!input) return null;
  // Extract the candidate segment.
  let segment = input;
  if (input.includes("://") || input.startsWith("/")) {
    try {
      const url = input.startsWith("/") ? `https://wol.jw.org${input}` : input;
      const u = new URL(url);
      segment = u.pathname.split("/").filter(Boolean)[0] ?? "";
    } catch {
      return null;
    }
  }
  const lower = segment.toLowerCase();
  // WOL legacy single-letter codes.
  if (lower === "e") return "en";
  if (lower === "s") return "es";
  if (lower === "t") return "pt";
  // Standard ISO-639-1 prefixes.
  if (lower.startsWith("es")) return "es";
  if (lower.startsWith("pt")) return "pt";
  if (lower.startsWith("en")) return "en";
  return null;
}
