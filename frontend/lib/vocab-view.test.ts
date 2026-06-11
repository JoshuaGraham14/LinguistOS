import assert from "node:assert/strict";
import { describe, it } from "node:test";
import {
  defaultViewConfig,
  orderedVisibleProperties,
} from "./vocab-view";

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
