// Re-exported from @jw-agent-toolkit/core to keep a single source of truth.
// The extension cannot define its own `Language` because verse_detector.ts
// imports `displayName(bookNum, lang: Language)` from the core package; the
// types would silently drift if redeclared here. F56.2.
export type { Language } from "@jw-agent-toolkit/core";
export type Template =
  | "plain"
  | "link"
  | "blockquote"
  | "callout"
  | "callout-collapsed";

export interface VerseMarkdownRequest {
  reference: string;
  language: Language;
  template: Template;
  length?: "short" | "medium" | "long";
  include_text?: boolean;
}

export interface VerseMarkdownResponse {
  markdown: string;
  reference: string;
  language: string;
  source_url: string;
  error?: string;
}

export interface CrossRefRequest {
  reference: string;
  language: Language;
}

export interface CrossRefHit {
  verse: string;
  url: string;
  excerpt?: string;
}

export interface CrossRefResponse {
  refs: CrossRefHit[];
  error?: string;
}

export interface VaultAppendRequest {
  reference: string;
  vault_path: string;
  template: Template;
  language: Language;
  subdir?: string;
}

export interface VaultAppendResponse {
  ok: boolean;
  path: string;
  error?: string;
}

export interface VerseTarget {
  /** Numeric verse number as printed on the page. */
  verseNum: number;
  /** Human reference such as `Juan 3:16`. */
  reference: string;
  /** The DOM node containing the verse text. */
  node: HTMLElement;
}
