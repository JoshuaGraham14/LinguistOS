/**
 * Shared filter shape for the Lexicon table view (LOS-301), the
 * flashcards filter mode (LOS-302), and any future view that wants to
 * pull a constrained slice of the canonical vocab.
 *
 * The serialized form (URL query string) is the persistence mechanism;
 * saved views (LOS-305) can layer on top later.
 */
import type { LanguageCode, VocabItem, VocabTag } from "./types";

export type DueFilter = "any" | "due_now" | "due_week" | "not_due";
export type LearnedFilter = "any" | "learned" | "not_learned";

export interface LexiconQuery {
  search: string;
  tags: VocabTag[];
  pos: string[];
  cefr: string[];
  learned: LearnedFilter;
  due: DueFilter;
  boxMin: number | null;
  boxMax: number | null;
  language: LanguageCode | null;
}

export const EMPTY_QUERY: LexiconQuery = {
  search: "",
  tags: [],
  pos: [],
  cefr: [],
  learned: "any",
  due: "any",
  boxMin: null,
  boxMax: null,
  language: null,
};

const ONE_DAY_MS = 24 * 60 * 60 * 1000;

function isWithin(target: number | null, msAhead: number) {
  if (target == null) return false;
  return target <= Date.now() + msAhead;
}

export function applyLexiconQuery(
  vocab: VocabItem[],
  query: LexiconQuery,
): VocabItem[] {
  let list = vocab;
  const q = query.search.trim().toLowerCase();
  if (q) {
    list = list.filter((v) => {
      const haystack = [
        v.word,
        v.translation,
        v.lemma ?? "",
        v.surfaceForm ?? "",
        v.glossPrimary ?? "",
        ...(v.glosses ?? []),
        ...(v.surfaceForms ?? []),
      ]
        .join(" ")
        .toLowerCase();
      return haystack.includes(q);
    });
  }
  if (query.tags.length > 0) {
    list = list.filter((v) => v.tags.some((t) => query.tags.includes(t)));
  }
  if (query.pos.length > 0) {
    list = list.filter((v) => v.pos != null && query.pos.includes(v.pos));
  }
  if (query.cefr.length > 0) {
    list = list.filter((v) => v.cefr != null && query.cefr.includes(v.cefr));
  }
  if (query.learned === "learned") list = list.filter((v) => v.learned);
  if (query.learned === "not_learned") list = list.filter((v) => !v.learned);
  if (query.boxMin != null) {
    const min = query.boxMin;
    list = list.filter((v) => (v.mastery?.box ?? 0) >= min);
  }
  if (query.boxMax != null) {
    const max = query.boxMax;
    list = list.filter((v) => (v.mastery?.box ?? 0) <= max);
  }
  if (query.due !== "any") {
    list = list.filter((v) => {
      const next = v.mastery?.nextDue ?? null;
      if (query.due === "not_due") return next == null || next > Date.now();
      if (query.due === "due_now") return isWithin(next, 0);
      if (query.due === "due_week") return isWithin(next, 7 * ONE_DAY_MS);
      return true;
    });
  }
  if (query.language) list = list.filter((v) => v.language === query.language);
  return list;
}

/**
 * Compact URL serialization. Empty/default values are omitted so common
 * shareable links stay short.
 */
export function serializeLexiconQuery(query: LexiconQuery): string {
  const params = new URLSearchParams();
  if (query.search) params.set("q", query.search);
  if (query.tags.length) params.set("tags", query.tags.join(","));
  if (query.pos.length) params.set("pos", query.pos.join(","));
  if (query.cefr.length) params.set("cefr", query.cefr.join(","));
  if (query.learned !== "any") params.set("learned", query.learned);
  if (query.due !== "any") params.set("due", query.due);
  if (query.boxMin != null) params.set("box_min", String(query.boxMin));
  if (query.boxMax != null) params.set("box_max", String(query.boxMax));
  if (query.language) params.set("lang", query.language);
  return params.toString();
}

const VALID_TAGS: ReadonlySet<VocabTag> = new Set<VocabTag>([
  "noun",
  "verb",
  "adjective",
  "adverb",
  "preposition",
  "other",
]);
const VALID_LANGUAGES: ReadonlySet<LanguageCode> = new Set<LanguageCode>([
  "es",
  "he",
  "fr",
]);
const VALID_LEARNED: ReadonlySet<LearnedFilter> = new Set<LearnedFilter>([
  "any",
  "learned",
  "not_learned",
]);
const VALID_DUE: ReadonlySet<DueFilter> = new Set<DueFilter>([
  "any",
  "due_now",
  "due_week",
  "not_due",
]);

function pickFromSet<T extends string>(
  raw: string | null,
  allowed: ReadonlySet<T>,
  fallback: T,
): T {
  if (raw && (allowed as ReadonlySet<string>).has(raw)) return raw as T;
  return fallback;
}

export function parseLexiconQuery(input: string | null): LexiconQuery {
  if (!input) return { ...EMPTY_QUERY };
  const params = new URLSearchParams(input);
  const csv = (key: string) =>
    (params.get(key) ?? "")
      .split(",")
      .map((s) => s.trim())
      .filter(Boolean);
  const num = (key: string) => {
    const v = params.get(key);
    if (v == null || v === "") return null;
    const n = Number(v);
    return Number.isFinite(n) ? n : null;
  };
  const language = pickFromSet(
    params.get("lang"),
    VALID_LANGUAGES,
    "" as LanguageCode,
  );
  return {
    search: params.get("q") ?? "",
    tags: csv("tags").filter((t): t is VocabTag =>
      (VALID_TAGS as ReadonlySet<string>).has(t),
    ),
    pos: csv("pos"),
    cefr: csv("cefr"),
    learned: pickFromSet(params.get("learned"), VALID_LEARNED, "any"),
    due: pickFromSet(params.get("due"), VALID_DUE, "any"),
    boxMin: num("box_min"),
    boxMax: num("box_max"),
    language: language || null,
  };
}

export function isEmptyLexiconQuery(query: LexiconQuery): boolean {
  return (
    !query.search &&
    query.tags.length === 0 &&
    query.pos.length === 0 &&
    query.cefr.length === 0 &&
    query.learned === "any" &&
    query.due === "any" &&
    query.boxMin == null &&
    query.boxMax == null &&
    query.language == null
  );
}
