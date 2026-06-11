import type { VocabItem, VocabTag } from "./types";

export interface WordFormInput {
  word: string;
  translation: string;
  tags: VocabTag[];
  surfaceForm?: string;
  glossPrimary?: string;
  glosses?: string[];
  lemma?: string;
  pos?: string | null;
  cefr?: string | null;
  frequencyRank?: number | null;
  gender?: string | null;
  conjugationClass?: string | null;
  morphFeatures?: Record<string, unknown> | null;
  ipa?: string | null;
  notes?: string | null;
}

const VALID_TAGS: VocabTag[] = [
  "noun",
  "verb",
  "adjective",
  "adverb",
  "preposition",
  "other",
];

function escapeCsv(value: string) {
  if (/[",\n]/.test(value)) return `"${value.replace(/"/g, '""')}"`;
  return value;
}

export function buildVocabCsv(items: VocabItem[]) {
  const lines = ["word,translation,tags,learned"];
  for (const item of items) {
    lines.push(
      [
        escapeCsv(item.word),
        escapeCsv(item.translation),
        escapeCsv(item.tags.join(";")),
        item.learned ? "true" : "false",
      ].join(","),
    );
  }
  return lines.join("\n") + "\n";
}

export function downloadVocabCsv(filename: string, contents: string) {
  const blob = new Blob([contents], { type: "text/csv;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
}

export function parseVocabImportText(text: string): WordFormInput[] {
  const rows: WordFormInput[] = [];
  for (const rawLine of text.split(/\r?\n/)) {
    const line = rawLine.trim();
    if (!line || line.startsWith("#")) continue;
    if (line.toLowerCase().startsWith("word,translation")) continue;
    const parts = line.split(",").map((p) => p.trim());
    if (parts.length < 2) continue;
    const [word, translation, rawTags] = parts;
    if (!word || !translation) continue;
    const tags: VocabTag[] = (rawTags ?? "")
      .split(";")
      .map((t) => t.trim().toLowerCase())
      .filter((t): t is VocabTag => (VALID_TAGS as string[]).includes(t));
    rows.push({ word, translation, tags });
  }
  return rows;
}
