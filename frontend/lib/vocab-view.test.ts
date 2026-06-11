import assert from "node:assert/strict";
import { describe, it } from "node:test";
import type { VocabItem } from "./types";
import {
  defaultViewConfig,
  orderedVisibleProperties,
  sortVocab,
} from "./vocab-view";

function item(
  overrides: Partial<VocabItem> & Pick<VocabItem, "id" | "word" | "createdAt">,
): VocabItem {
  return {
    workspaceId: 1,
    lexemeId: null,
    enriching: false,
    translation: "",
    language: "es",
    tags: [],
    learned: false,
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

describe("defaultViewConfig", () => {
  it("includes table columns for new table views", () => {
    const config = defaultViewConfig("table");
    assert.ok(config.visibleProperties.includes("word"));
    assert.ok(config.visibleProperties.includes("translation"));
    assert.equal(config.sorts[0]?.field, "createdAt");
  });

  it("groups board views by learned by default", () => {
    const config = defaultViewConfig("board");
    assert.equal(config.groupBy, "learned");
  });
});

describe("sortVocab", () => {
  it("defaults to Date Added descending when sorts is empty", () => {
    const vocab = [
      item({ id: 1, word: "older", createdAt: 100 }),
      item({ id: 2, word: "newer", createdAt: 200 }),
    ];
    const result = sortVocab(vocab, []);
    assert.deepEqual(
      result.map((v) => v.id),
      [2, 1],
    );
  });

  it("respects explicit sorts over the default", () => {
    const vocab = [
      item({ id: 1, word: "beta", createdAt: 200 }),
      item({ id: 2, word: "alpha", createdAt: 100 }),
    ];
    const result = sortVocab(vocab, [{ field: "word", direction: "asc" }]);
    assert.deepEqual(
      result.map((v) => v.id),
      [2, 1],
    );
  });
});

describe("orderedVisibleProperties", () => {
  it("always includes word as the first column", () => {
    const columns = orderedVisibleProperties({
      query: {
        search: "",
        tags: [],
        pos: [],
        cefr: [],
        learned: "any",
        due: "any",
        statusMatch: "all",
        boxMin: null,
        boxMax: null,
        language: null,
      },
      sorts: [],
      groupBy: null,
      visibleProperties: ["translation", "pos"],
      propertyOrder: ["translation", "pos"],
    });
    assert.deepEqual(columns[0], "word");
    assert.ok(columns.includes("translation"));
  });
});
