export type VocabTag =
  | "noun"
  | "verb"
  | "adjective"
  | "adverb"
  | "preposition"
  | "other";

export interface VocabItem {
  id: string;
  word: string;
  translation: string;
  language: "es";
  tags: VocabTag[];
  learned: boolean;
  createdAt: number;
}

export interface PracticeSettings {
  mode: "typing" | "multiple-choice";
  direction: "en-to-es" | "es-to-en";
  sentenceLength: "short" | "medium" | "long";
  tagFilter: VocabTag[];
}

export interface SentenceCandidate {
  sentence: string;
  translation?: string;
  score: number;
  features?: Record<string, unknown>;
}
