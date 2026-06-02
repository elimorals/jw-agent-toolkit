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
}
