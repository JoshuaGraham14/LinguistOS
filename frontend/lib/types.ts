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

export type Tense =
  | "present"
  | "preterite"
  | "imperfect"
  | "future"
  | "conditional"
  | "subjunctive";

export type Person = "1st" | "2nd" | "3rd";

export type GrammaticalNumber = "singular" | "plural";

export interface PracticeSettings {
  mode: "typing" | "multiple-choice";
  direction: "en-to-es" | "es-to-en";
  sentenceLength: "short" | "medium" | "long";
  tagFilter: VocabTag[];
  tense: Tense;
  person: Person;
  number: GrammaticalNumber;
}

export interface SentenceCandidate {
  sentence: string;
  translation?: string;
  score: number;
  features?: Record<string, unknown>;
}

export interface Profile {
  name: string;
}
