import assert from "node:assert/strict";
import { describe, it } from "node:test";
import type { VocabItem } from "./types";
import {
  canHideProperty,
  defaultViewConfig,
  hideAllProperties,
  hideProperty,
  orderedPropertyKeys,
  orderedVisibleProperties,
  removeSortRule,
  reorderPropertyKeys,
  setPrimarySortRule,
  showAllProperties,
  showProperty,
  sortVocab,
  type VocabViewConfig,
} from "./vocab-view";

const EMPTY_QUERY = {
  search: "",
  tags: [],
  pos: [],
  cefr: [],
  learned: "any" as const,
  due: "any" as const,
  statusMatch: "all" as const,
  boxMin: null,
  boxMax: null,
  language: null,
};

function viewConfig(
  overrides: Partial<VocabViewConfig> = {},
): VocabViewConfig {
  return {
    query: { ...EMPTY_QUERY },
    sorts: [],
    groupBy: null,
    visibleProperties: ["word", "translation", "pos"],
    propertyOrder: ["word", "translation", "pos"],
    ...overrides,
  };
}

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
    const columns = orderedVisibleProperties(
      viewConfig({
        visibleProperties: ["translation", "pos"],
        propertyOrder: ["translation", "pos"],
      }),
    );
    assert.deepEqual(columns[0], "word");
    assert.ok(columns.includes("translation"));
  });

  it("deduplicates repeated property keys in saved config", () => {
    const columns = orderedVisibleProperties(
      viewConfig({
        visibleProperties: ["word", "translation", "createdAt", "createdAt"],
        propertyOrder: ["word", "translation", "createdAt", "createdAt"],
      }),
    );
    assert.deepEqual(
      columns.filter((key) => key === "createdAt").length,
      1,
    );
  });
});

describe("column menu helpers", () => {
  it("prevents hiding the title column", () => {
    assert.equal(canHideProperty("word"), false);
    const next = hideProperty(viewConfig(), "word");
    assert.ok(next.visibleProperties.includes("word"));
  });

  it("hides and shows non-title columns", () => {
    const hidden = hideProperty(viewConfig(), "pos");
    assert.ok(!hidden.visibleProperties.includes("pos"));
    const shown = showProperty(hidden, "pos");
    assert.ok(shown.visibleProperties.includes("pos"));
  });

  it("sets and removes primary sort rules", () => {
    const sorted = setPrimarySortRule([], "cefr", "asc");
    assert.deepEqual(sorted, [{ field: "cefr", direction: "asc" }]);
    const cleared = removeSortRule(sorted, "cefr");
    assert.deepEqual(cleared, []);
  });

  it("shows and hides all hideable properties", () => {
    const hidden = hideAllProperties(viewConfig());
    assert.deepEqual(hidden.visibleProperties, ["word"]);
    const shown = showAllProperties(hidden);
    assert.ok(shown.visibleProperties.includes("translation"));
    assert.ok(shown.visibleProperties.includes("pos"));
  });

  it("reorders properties and reflects in visible column order", () => {
    const base = viewConfig({
      visibleProperties: ["word", "translation", "pos"],
      propertyOrder: ["word", "translation", "pos"],
    });
    const reordered = reorderPropertyKeys(base, "pos", "word");
    assert.deepEqual(orderedPropertyKeys(reordered).slice(0, 3), [
      "pos",
      "word",
      "translation",
    ]);
    assert.deepEqual(orderedVisibleProperties(reordered), [
      "word",
      "pos",
      "translation",
    ]);
  });
});
