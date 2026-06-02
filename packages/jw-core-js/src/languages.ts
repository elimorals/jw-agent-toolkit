/**
 * Per-language configuration used to assemble wol.jw.org URLs.
 *
 * Matches `jw_core.languages` semantics for the three core locales. The JW
 * URL schema uses an internal language tag (`lp_tag`) and a publication
 * code (`default_bible`) that differ between English (`nwtsty`) and the
 * other languages (`nwt`). See `jw_core/models.py:BibleRef.wol_url` for
 * the canonical implementation in Python.
 */

import type { Language } from "./books.js";

export interface LanguageConfig {
  iso: Language;
  wolResource: string;
  lpTag: string;
  defaultBible: string;
}

const TABLE: Record<Language, LanguageConfig> = {
  en: {
    iso: "en",
    wolResource: "r1",
    lpTag: "lp-e",
    defaultBible: "nwtsty",
  },
  es: {
    iso: "es",
    wolResource: "r4",
    lpTag: "lp-s",
    defaultBible: "nwt",
  },
  pt: {
    iso: "pt",
    wolResource: "r5",
    lpTag: "lp-t",
    defaultBible: "nwt",
  },
};

export function getLanguageConfig(lang: Language): LanguageConfig {
  return TABLE[lang];
}
