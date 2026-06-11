import {
  applyLexiconQuery,
  EMPTY_QUERY,
  type LexiconQuery,
} from "./lexicon-query";
import type { SavedViewLayout, SortDirection, SortRule, VocabItem } from "./types";

export interface VocabViewConfig {
  query: LexiconQuery;
  sorts: SortRule[];
  groupBy: string | null;
  visibleProperties: string[];
  propertyOrder: string[];
}

export const DEFAULT_SORTS: SortRule[] = [
  { field: "createdAt", direction: "desc" },
];

export const EMPTY_VIEW_CONFIG: VocabViewConfig = {
  query: { ...EMPTY_QUERY },
  sorts: [],
  groupBy: null,
  visibleProperties: [],
  propertyOrder: [],
};

export function effectiveSorts(sorts: SortRule[]): SortRule[] {
  return sorts.length > 0 ? sorts : DEFAULT_SORTS;
}

const TABLE_PROPERTIES = [
  "word",
  "lemma",
  "translation",
  "pos",
  "cefr",
  "tags",
  "createdAt",
  "box",
  "nextDue",
];

const GALLERY_PROPERTIES = ["word", "translation", "tags", "learned"];

const BOARD_PROPERTIES = ["word", "translation"];

export function defaultViewConfig(layout: SavedViewLayout): VocabViewConfig {
  const visible =
    layout === "gallery"
      ? GALLERY_PROPERTIES
      : layout === "board"
        ? BOARD_PROPERTIES
        : TABLE_PROPERTIES;
  return {
    query: { ...EMPTY_QUERY },
    sorts: [...DEFAULT_SORTS],
    groupBy: layout === "board" ? "learned" : null,
    visibleProperties: [...visible],
    propertyOrder: [...visible],
  };
}

export function isEmptyViewConfig(config: VocabViewConfig): boolean {
  return (
    config.visibleProperties.length === 0 && config.propertyOrder.length === 0
  );
}

export interface VocabGroup {
  key: string;
  label: string;
  items: VocabItem[];
}

function sortValue(item: VocabItem, field: string): string | number | boolean | null {
  switch (field) {
    case "word":
      return item.word.toLowerCase();
    case "lemma":
      return (item.lemma ?? item.word).toLowerCase();
    case "translation":
      return (item.glossPrimary || item.translation).toLowerCase();
    case "pos":
      return item.pos?.toLowerCase() ?? "";
    case "cefr":
      return item.cefr ?? "";
    case "learned":
      return item.learned ? 1 : 0;
    case "box":
      return item.mastery?.box ?? 0;
    case "nextDue":
      return item.mastery?.nextDue ?? Number.MAX_SAFE_INTEGER;
    case "createdAt":
      return item.createdAt;
    case "gender":
      return item.gender ?? "";
    case "ipa":
      return item.ipa ?? "";
    default:
      return item.word.toLowerCase();
  }
}

function compareValues(
  a: string | number | boolean | null,
  b: string | number | boolean | null,
  direction: SortDirection,
): number {
  const mul = direction === "asc" ? 1 : -1;
  if (a === b) return 0;
  if (a == null) return 1 * mul;
  if (b == null) return -1 * mul;
  if (typeof a === "string" && typeof b === "string") {
    return a.localeCompare(b) * mul;
  }
  if (a < b) return -1 * mul;
  if (a > b) return 1 * mul;
  return 0;
}

export function sortVocab(items: VocabItem[], sorts: SortRule[]): VocabItem[] {
  const rules = effectiveSorts(sorts);
  return [...items].sort((left, right) => {
    for (const rule of rules) {
      const cmp = compareValues(
        sortValue(left, rule.field),
        sortValue(right, rule.field),
        rule.direction,
      );
      if (cmp !== 0) return cmp;
    }
    return 0;
  });
}

function groupLabel(key: string, field: string): string {
  if (field === "learned") return key === "true" ? "Learned" : "Still learning";
  if (key === "") return "—";
  return key;
}

function groupKey(item: VocabItem, field: string): string {
  switch (field) {
    case "learned":
      return String(item.learned);
    case "cefr":
      return item.cefr ?? "";
    case "pos":
      return item.pos ?? "";
    case "box":
      return String(item.mastery?.box ?? 0);
    case "tags":
      return item.tags[0] ?? "";
    default:
      return "";
  }
}

export function groupVocab(
  items: VocabItem[],
  groupBy: string | null,
): VocabGroup[] | null {
  if (!groupBy) return null;
  const buckets = new Map<string, VocabItem[]>();
  for (const item of items) {
    const key = groupKey(item, groupBy);
    const list = buckets.get(key) ?? [];
    list.push(item);
    buckets.set(key, list);
  }
  return [...buckets.entries()]
    .sort(([a], [b]) => a.localeCompare(b))
    .map(([key, groupItems]) => ({
      key,
      label: groupLabel(key, groupBy),
      items: groupItems,
    }));
}

export function applyViewPipeline(
  vocab: VocabItem[],
  config: VocabViewConfig,
): { items: VocabItem[]; groups: VocabGroup[] | null } {
  const filtered = applyLexiconQuery(vocab, config.query);
  const sorted = sortVocab(filtered, config.sorts);
  const groups = groupVocab(sorted, config.groupBy);
  return { items: sorted, groups };
}

export function orderedVisibleProperties(config: VocabViewConfig): string[] {
  const visible = new Set(config.visibleProperties);
  visible.add("word");
  const ordered = config.propertyOrder.filter((key) => visible.has(key));
  for (const key of config.visibleProperties) {
    if (!ordered.includes(key)) ordered.push(key);
  }
  if (!ordered.includes("word")) {
    ordered.unshift("word");
  } else {
    const wordIndex = ordered.indexOf("word");
    if (wordIndex > 0) {
      ordered.splice(wordIndex, 1);
      ordered.unshift("word");
    }
  }
  return ordered;
}
