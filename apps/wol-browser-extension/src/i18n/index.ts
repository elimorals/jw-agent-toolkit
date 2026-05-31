import type { Language } from "../types";

import en from "./en.json";
import es from "./es.json";
import pt from "./pt.json";

type Messages = Record<string, string>;

const TABLES: Record<Language, Messages> = {
  en: en as Messages,
  es: es as Messages,
  pt: pt as Messages,
};

export function createTranslator(lang: Language) {
  const dict = TABLES[lang] ?? TABLES.en;
  return function t(key: string, params: Record<string, string> = {}): string {
    const raw = dict[key] ?? TABLES.en[key] ?? key;
    return raw.replace(/\{(\w+)\}/g, (_, k: string) => params[k] ?? `{${k}}`);
  };
}

const URL_LANG_MAP: Record<string, Language> = {
  en: "en",
  es: "es",
  t: "pt", // wol uses /t/ for Portuguese
  pt: "pt",
};

export function detectLanguage(href: string): Language {
  try {
    const u = new URL(href);
    const seg = u.pathname.split("/").filter(Boolean)[0] ?? "en";
    return URL_LANG_MAP[seg] ?? "en";
  } catch {
    return "en";
  }
}
