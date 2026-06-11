import assert from "node:assert/strict";
import { describe, it } from "node:test";
import { applyLexiconQuery } from "./lexicon-query";
import type { MasteryState, VocabItem } from "./types";

function mastery(
  overrides: Partial<MasteryState> & Pick<MasteryState, "box" | "nextDue">,
): MasteryState {
  return {
    strength: 0,
    lastReviewedAt: null,
    streak: 0,
    failures: 0,
    successes: 0,
    ...overrides,
  };
}

function item(
  overrides: Partial<VocabItem> & Pick<VocabItem, "id" | "word">,
): VocabItem {
  return {
    workspaceId: 1,
    lexemeId: null,
    enriching: false,
    translation: "",
    language: "es",
    tags: [],
    learned: false,
    createdAt: 0,
    lemma: null,
    surfaceForm: null,
    surfaceForms: [],
    pos: null,
    cefr: null,
    frequencyRank: null,
    gender: null,
    conjugationClass: null,
    morphFeatures: null,
    ipa: null,
    audioUrl: null,
    imageUrl: null,
    glossPrimary: null,
    glosses: [],
    notes: null,
    lastSeenAt: null,
    mastery: null,
    ...overrides,
  };
}

describe("applyLexiconQuery statusMatch", () => {
  const vocab = [
    item({
      id: 1,
      word: "a",
      learned: false,
      mastery: mastery({ box: 1, nextDue: Date.now() - 1000 }),
    }),
    item({
      id: 2,
      word: "b",
      learned: true,
      mastery: mastery({ box: 3, nextDue: Date.now() + 1_000_000 }),
    }),
    item({
      id: 3,
      word: "c",
      learned: true,
      mastery: mastery({ box: 2, nextDue: Date.now() - 1000 }),
    }),
  ];

  it("uses AND for learned and due when statusMatch is all", () => {
    const result = applyLexiconQuery(vocab, {
      search: "",
      tags: [],
      pos: [],
      cefr: [],
      learned: "not_learned",
      due: "due_now",
      statusMatch: "all",
      boxMin: null,
      boxMax: null,
      language: null,
    });
    assert.deepEqual(
      result.map((v) => v.id),
      [1],
    );
  });

  it("uses OR for learned and due when statusMatch is any", () => {
    const result = applyLexiconQuery(vocab, {
      search: "",
      tags: [],
      pos: [],
      cefr: [],
      learned: "not_learned",
      due: "due_now",
      statusMatch: "any",
      boxMin: null,
      boxMax: null,
      language: null,
    });
    assert.deepEqual(
      result.map((v) => v.id),
      [1, 3],
    );
  });
});
