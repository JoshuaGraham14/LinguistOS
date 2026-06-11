import type { VocabItem } from "./types";

export type PropertyType =
  | "title"
  | "text"
  | "select"
  | "multi_select"
  | "number"
  | "date"
  | "checkbox";

export interface VocabPropertyDef {
  key: string;
  label: string;
  type: PropertyType;
  sortable: boolean;
  groupable: boolean;
  writable: boolean;
  /** Title property is always shown and links to the word page. */
  isTitle?: boolean;
  getValue: (item: VocabItem) => string | number | boolean | null;
}

export const VOCAB_PROPERTIES: VocabPropertyDef[] = [
  {
    key: "word",
    label: "Word",
    type: "title",
    sortable: true,
    groupable: false,
    writable: false,
    isTitle: true,
    getValue: (item) => item.word,
  },
  {
    key: "lemma",
    label: "Lemma",
    type: "text",
    sortable: true,
    groupable: false,
    writable: false,
    getValue: (item) => item.lemma ?? item.word,
  },
  {
    key: "translation",
    label: "Translation",
    type: "text",
    sortable: true,
    groupable: false,
    writable: false,
    getValue: (item) => item.glossPrimary || item.translation,
  },
  {
    key: "pos",
    label: "POS",
    type: "select",
    sortable: true,
    groupable: true,
    writable: false,
    getValue: (item) => item.pos,
  },
  {
    key: "cefr",
    label: "CEFR",
    type: "select",
    sortable: true,
    groupable: true,
    writable: true,
    getValue: (item) => item.cefr,
  },
  {
    key: "tags",
    label: "Tags",
    type: "multi_select",
    sortable: false,
    groupable: true,
    writable: false,
    getValue: (item) => item.tags.join(", "),
  },
  {
    key: "gender",
    label: "Gender",
    type: "select",
    sortable: true,
    groupable: true,
    writable: false,
    getValue: (item) => item.gender,
  },
  {
    key: "ipa",
    label: "IPA",
    type: "text",
    sortable: true,
    groupable: false,
    writable: false,
    getValue: (item) => item.ipa,
  },
  {
    key: "learned",
    label: "Learned",
    type: "checkbox",
    sortable: true,
    groupable: true,
    writable: true,
    getValue: (item) => item.learned,
  },
  {
    key: "box",
    label: "Box",
    type: "number",
    sortable: true,
    groupable: true,
    writable: false,
    getValue: (item) => item.mastery?.box ?? 0,
  },
  {
    key: "nextDue",
    label: "Next due",
    type: "date",
    sortable: true,
    groupable: false,
    writable: false,
    getValue: (item) => item.mastery?.nextDue ?? null,
  },
  {
    key: "createdAt",
    label: "Date Added",
    type: "date",
    sortable: true,
    groupable: false,
    writable: false,
    getValue: (item) => item.createdAt,
  },
];

const PROPERTY_MAP = new Map(VOCAB_PROPERTIES.map((p) => [p.key, p]));

export function getVocabProperty(key: string): VocabPropertyDef | undefined {
  return PROPERTY_MAP.get(key);
}

export function groupableProperties(): VocabPropertyDef[] {
  return VOCAB_PROPERTIES.filter((p) => p.groupable);
}

export function sortableProperties(): VocabPropertyDef[] {
  return VOCAB_PROPERTIES.filter((p) => p.sortable);
}
