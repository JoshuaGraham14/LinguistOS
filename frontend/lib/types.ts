export type VocabTag =
  | "noun"
  | "verb"
  | "adjective"
  | "adverb"
  | "preposition"
  | "other";

export type MasteryOutcome = "correct" | "incorrect" | "skipped" | "hinted";

export interface MasteryState {
  strength: number;
  box: number;
  lastReviewedAt: number | null;
  nextDue: number | null;
  streak: number;
  failures: number;
  successes: number;
}

export interface VocabItem {
  id: number;
  workspaceId: number;
  word: string;
  translation: string;
  language: LanguageCode;
  tags: VocabTag[];
  learned: boolean;
  createdAt: number;

  // Canonical fields (LOS-101). Nullable until backfill / enrichment fills them.
  lemma: string | null;
  surfaceForm: string | null;
  surfaceForms: string[];
  pos: string | null;
  cefr: string | null;
  frequencyRank: number | null;
  gender: string | null;
  conjugationClass: string | null;
  morphFeatures: Record<string, unknown> | null;
  ipa: string | null;
  audioUrl: string | null;
  imageUrl: string | null;
  glossPrimary: string | null;
  glosses: string[];
  notes: string | null;
  lastSeenAt: number | null;

  mastery: MasteryState | null;
}

export type LanguageCode =
  | "es"
  | "he"
  | "fr";

export type WordDisplayMode = "lemma_first" | "as_encountered";

export interface Workspace {
  id: number;
  ownerId: number;
  name: string;
  language: LanguageCode;
  emojiOrFlag: string;
  createdAt: number;
  updatedAt: number;
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
  wordDisplayMode: WordDisplayMode;
}
