/**
 * Versification mapping — minimal port of the Python `jw_core.versification`
 * module (Fase 46). Maps a (book, chapter, verseStart, verseEnd) tuple
 * between nwt / masoretic / lxx / vulgate using the same JSON catalog the
 * Python implementation ships.
 *
 * Idempotent: `toCanonical({...from: X, to: X})` returns the input
 * unchanged with `isDiscrepant=false`.
 *
 * Lossless on round-trip for cataloged entries.
 */

import catalog from "./versification_map.json" with { type: "json" };

export type Tradition = "nwt" | "masoretic" | "lxx" | "vulgate";

export type VersificationIssue =
  | "superscription"
  | "chapter_split"
  | "verse_split"
  | "verse_merge"
  | "chapter_renumber"
  | "verse_shift";

export interface VerseCoord {
  chapter: number;
  verseStart: number;
  verseEnd?: number | null;
}

export interface VersificationEntry {
  book: string;
  book_num: number;
  issue: VersificationIssue;
  nwt: VerseCoord;
  masoretic?: VerseCoord;
  lxx?: VerseCoord;
  vulgate?: VerseCoord;
  source: string;
  explanation: Record<"en" | "es" | "pt", string>;
}

interface RawCoord {
  chapter: number;
  verse_start: number;
  verse_end?: number | null;
}

interface RawEntry {
  book: string;
  book_num: number;
  issue: VersificationIssue;
  nwt: RawCoord;
  masoretic?: RawCoord;
  lxx?: RawCoord;
  vulgate?: RawCoord;
  source: string;
  explanation: Record<"en" | "es" | "pt", string>;
}

interface RawCatalog {
  version: string;
  discrepancies: RawEntry[];
}

function toCoord(raw: RawCoord | undefined): VerseCoord | undefined {
  if (!raw) return undefined;
  return {
    chapter: raw.chapter,
    verseStart: raw.verse_start,
    verseEnd: raw.verse_end ?? null,
  };
}

function normalizeEntry(raw: RawEntry): VersificationEntry {
  const out: VersificationEntry = {
    book: raw.book,
    book_num: raw.book_num,
    issue: raw.issue,
    nwt: toCoord(raw.nwt) as VerseCoord,
    source: raw.source,
    explanation: raw.explanation,
  };
  const masoretic = toCoord(raw.masoretic);
  const lxx = toCoord(raw.lxx);
  const vulgate = toCoord(raw.vulgate);
  if (masoretic) out.masoretic = masoretic;
  if (lxx) out.lxx = lxx;
  if (vulgate) out.vulgate = vulgate;
  return out;
}

let cachedEntries: readonly VersificationEntry[] | null = null;

export function loadCatalog(): readonly VersificationEntry[] {
  if (cachedEntries == null) {
    const raw = catalog as RawCatalog;
    cachedEntries = raw.discrepancies.map(normalizeEntry);
  }
  return cachedEntries;
}

export const CATALOG_VERSION: string = (catalog as RawCatalog).version;

const TRADITIONS: readonly Tradition[] = ["nwt", "masoretic", "lxx", "vulgate"];

function coordFor(
  entry: VersificationEntry,
  tradition: Tradition,
): VerseCoord | undefined {
  return entry[tradition];
}

export interface MappingResult {
  refBook: string;
  refBookNum: number;
  coord: VerseCoord;
  fromTradition: Tradition;
  toTradition: Tradition;
  isDiscrepant: boolean;
  rationale: string | null;
}

export interface ToCanonicalArgs {
  book: string;
  bookNum: number;
  chapter: number;
  verseStart: number;
  verseEnd?: number | null;
  fromTradition?: Tradition;
  toTradition: Tradition;
}

/**
 * Map a coordinate between numbering traditions.
 *
 * Throws RangeError when either tradition is unknown.
 */
export function toCanonical(args: ToCanonicalArgs): MappingResult {
  const fromTradition = args.fromTradition ?? "nwt";
  if (!TRADITIONS.includes(fromTradition)) {
    throw new RangeError(`Unknown fromTradition: ${fromTradition}`);
  }
  if (!TRADITIONS.includes(args.toTradition)) {
    throw new RangeError(`Unknown toTradition: ${args.toTradition}`);
  }

  const coord: VerseCoord = {
    chapter: args.chapter,
    verseStart: args.verseStart,
    verseEnd: args.verseEnd ?? null,
  };

  if (fromTradition === args.toTradition) {
    return {
      refBook: args.book,
      refBookNum: args.bookNum,
      coord,
      fromTradition,
      toTradition: args.toTradition,
      isDiscrepant: false,
      rationale: null,
    };
  }

  const entries = loadCatalog();
  let matched: VersificationEntry | null = null;
  for (const entry of entries) {
    if (entry.book_num !== args.bookNum) continue;
    const src = coordFor(entry, fromTradition);
    const dst = coordFor(entry, args.toTradition);
    if (!src || !dst) continue;
    if (src.chapter !== coord.chapter) continue;
    if (src.verseStart !== coord.verseStart) continue;
    matched = entry;
    break;
  }

  if (!matched) {
    return {
      refBook: args.book,
      refBookNum: args.bookNum,
      coord,
      fromTradition,
      toTradition: args.toTradition,
      isDiscrepant: false,
      rationale: null,
    };
  }

  const src = coordFor(matched, fromTradition) as VerseCoord;
  const dst = coordFor(matched, args.toTradition) as VerseCoord;

  const chapterDelta = dst.chapter - src.chapter;
  const verseDelta = dst.verseStart - src.verseStart;

  const newChapter = Math.max(0, coord.chapter + chapterDelta);
  const newStart = Math.max(0, coord.verseStart + verseDelta);
  const newEnd =
    coord.verseEnd != null ? Math.max(0, coord.verseEnd + verseDelta) : null;

  return {
    refBook: matched.book,
    refBookNum: matched.book_num,
    coord: { chapter: newChapter, verseStart: newStart, verseEnd: newEnd },
    fromTradition,
    toTradition: args.toTradition,
    isDiscrepant: true,
    rationale: matched.explanation.en,
  };
}

export type Language = "en" | "es" | "pt";

/** Trilingual rationale for the discrepancy at this coordinate. */
export function explain(args: ToCanonicalArgs & { language?: Language }): string | null {
  const fromTradition = args.fromTradition ?? "nwt";
  if (fromTradition === args.toTradition) return null;
  const result = toCanonical(args);
  if (!result.isDiscrepant) return null;
  const language: Language = args.language ?? "en";
  for (const entry of loadCatalog()) {
    if (entry.book_num !== args.bookNum) continue;
    const src = coordFor(entry, fromTradition);
    if (!src) continue;
    if (src.chapter === args.chapter && src.verseStart === args.verseStart) {
      return entry.explanation[language] || entry.explanation.en;
    }
  }
  return null;
}
