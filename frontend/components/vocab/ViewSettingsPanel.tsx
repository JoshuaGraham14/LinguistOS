"use client";

import { X } from "lucide-react";
import { cn } from "@/lib/cn";
import {
  EMPTY_QUERY,
  isEmptyLexiconQuery,
  type DueFilter,
  type LearnedFilter,
  type LexiconQuery,
} from "@/lib/lexicon-query";
import type {
  SavedViewLayout,
  SortDirection,
  SortRule,
  VocabTag,
} from "@/lib/types";
import {
  groupableProperties,
  sortableProperties,
  VOCAB_PROPERTIES,
} from "@/lib/vocab-properties";
import type { VocabViewConfig } from "@/lib/vocab-view";

const TAG_OPTIONS: VocabTag[] = [
  "noun",
  "verb",
  "adjective",
  "adverb",
  "preposition",
  "other",
];
const POS_OPTIONS = ["noun", "verb", "adjective", "adverb", "preposition"];
const CEFR_OPTIONS = ["A1", "A2", "B1", "B2", "C1", "C2"];
const LAYOUT_OPTIONS: { value: SavedViewLayout; label: string }[] = [
  { value: "table", label: "Table" },
  { value: "gallery", label: "Gallery" },
  { value: "board", label: "Board" },
];

const LEARNED_LABELS: Record<LearnedFilter, string> = {
  any: "All",
  learned: "Learned",
  not_learned: "Still learning",
};

const DUE_LABELS: Record<DueFilter, string> = {
  any: "Any due",
  due_now: "Due now",
  due_week: "Due this week",
  not_due: "Not due",
};

export type ViewSettingsSection =
  | "layout"
  | "properties"
  | "filter"
  | "sort"
  | "group";

function toggleInList<T extends string>(list: T[], value: T): T[] {
  if (list.includes(value)) return list.filter((v) => v !== value);
  return [...list, value];
}

function FilterSection({
  query,
  onChange,
}: {
  query: LexiconQuery;
  onChange: (query: LexiconQuery) => void;
}) {
  return (
    <div className="space-y-4">
      <div className="flex items-center gap-2 flex-wrap">
        <span className="text-xs uppercase tracking-wide text-slate-500 w-full">
          Tags
        </span>
        {TAG_OPTIONS.map((tag) => (
          <button
            key={tag}
            type="button"
            onClick={() =>
              onChange({ ...query, tags: toggleInList(query.tags, tag) })
            }
            className={cn(
              "px-2.5 py-1 rounded-full text-xs border transition capitalize",
              query.tags.includes(tag)
                ? "bg-brand-100 border-brand-300 text-brand-700"
                : "bg-white border-slate-200 text-slate-600 hover:bg-slate-50",
            )}
          >
            {tag}
          </button>
        ))}
      </div>
      <div className="flex items-center gap-2 flex-wrap">
        <span className="text-xs uppercase tracking-wide text-slate-500 w-full">
          POS
        </span>
        {POS_OPTIONS.map((pos) => (
          <button
            key={pos}
            type="button"
            onClick={() =>
              onChange({ ...query, pos: toggleInList(query.pos, pos) })
            }
            className={cn(
              "px-2.5 py-1 rounded-full text-xs border transition capitalize",
              query.pos.includes(pos)
                ? "bg-emerald-100 border-emerald-300 text-emerald-700"
                : "bg-white border-slate-200 text-slate-600 hover:bg-slate-50",
            )}
          >
            {pos}
          </button>
        ))}
      </div>
      <div className="flex items-center gap-2 flex-wrap">
        <span className="text-xs uppercase tracking-wide text-slate-500 w-full">
          CEFR
        </span>
        {CEFR_OPTIONS.map((c) => (
          <button
            key={c}
            type="button"
            onClick={() =>
              onChange({ ...query, cefr: toggleInList(query.cefr, c) })
            }
            className={cn(
              "px-2.5 py-1 rounded-full text-xs border transition",
              query.cefr.includes(c)
                ? "bg-fuchsia-100 border-fuchsia-300 text-fuchsia-700"
                : "bg-white border-slate-200 text-slate-600 hover:bg-slate-50",
            )}
          >
            {c}
          </button>
        ))}
      </div>
      <div className="flex items-center gap-2 flex-wrap">
        <span className="text-xs uppercase tracking-wide text-slate-500 w-full">
          Learned
        </span>
        {(Object.keys(LEARNED_LABELS) as LearnedFilter[]).map((f) => (
          <button
            key={f}
            type="button"
            onClick={() => onChange({ ...query, learned: f })}
            className={cn(
              "px-2.5 py-1 rounded-full text-xs border transition",
              query.learned === f
                ? "bg-amber-100 border-amber-300 text-amber-700"
                : "bg-white border-slate-200 text-slate-600 hover:bg-slate-50",
            )}
          >
            {LEARNED_LABELS[f]}
          </button>
        ))}
      </div>
      <div className="flex items-center gap-2 flex-wrap">
        <span className="text-xs uppercase tracking-wide text-slate-500 w-full">
          Due
        </span>
        {(Object.keys(DUE_LABELS) as DueFilter[]).map((f) => (
          <button
            key={f}
            type="button"
            onClick={() => onChange({ ...query, due: f })}
            className={cn(
              "px-2.5 py-1 rounded-full text-xs border transition",
              query.due === f
                ? "bg-rose-100 border-rose-300 text-rose-700"
                : "bg-white border-slate-200 text-slate-600 hover:bg-slate-50",
            )}
          >
            {DUE_LABELS[f]}
          </button>
        ))}
      </div>
      {!isEmptyLexiconQuery(query) && (
        <button
          type="button"
          onClick={() => onChange({ ...EMPTY_QUERY })}
          className="text-xs text-slate-500 hover:text-slate-700"
        >
          Reset filters
        </button>
      )}
    </div>
  );
}

export function ViewSettingsPanel({
  open,
  section,
  layout,
  config,
  onLayoutChange,
  onConfigChange,
  onClose,
}: {
  open: boolean;
  section: ViewSettingsSection | null;
  layout: SavedViewLayout;
  config: VocabViewConfig;
  onLayoutChange: (layout: SavedViewLayout) => void;
  onConfigChange: (updater: (prev: VocabViewConfig) => VocabViewConfig) => void;
  onClose: () => void;
}) {
  if (!open) return null;

  const visibleCount = config.visibleProperties.length;

  function updateSorts(sorts: SortRule[]) {
    onConfigChange((prev) => ({ ...prev, sorts }));
  }

  function toggleProperty(key: string) {
    onConfigChange((prev) => {
      const visible = prev.visibleProperties.includes(key)
        ? prev.visibleProperties.filter((k) => k !== key)
        : [...prev.visibleProperties, key];
      const order = prev.propertyOrder.includes(key)
        ? prev.propertyOrder
        : [...prev.propertyOrder, key];
      return { ...prev, visibleProperties: visible, propertyOrder: order };
    });
  }

  return (
    <aside className="w-72 shrink-0 glass-card rounded-2xl p-4 space-y-4 overflow-y-auto max-h-[calc(100vh-12rem)]">
      <div className="flex items-center justify-between">
        <h2 className="text-sm font-semibold text-slate-900">View settings</h2>
        <button
          type="button"
          onClick={onClose}
          className="p-1 rounded-lg text-slate-400 hover:text-slate-600 hover:bg-slate-100"
        >
          <X className="h-4 w-4" />
        </button>
      </div>

      {(section === null || section === "layout") && (
        <div className="space-y-2">
          <h3 className="text-xs font-medium uppercase tracking-wide text-slate-500">
            Layout
          </h3>
          <div className="flex flex-col gap-1">
            {LAYOUT_OPTIONS.map((opt) => (
              <button
                key={opt.value}
                type="button"
                onClick={() => onLayoutChange(opt.value)}
                className={cn(
                  "text-left px-3 py-2 rounded-lg text-sm transition",
                  layout === opt.value
                    ? "bg-brand-50 text-brand-700 font-medium"
                    : "text-slate-600 hover:bg-slate-50",
                )}
              >
                {opt.label}
              </button>
            ))}
          </div>
        </div>
      )}

      {(section === null || section === "properties") && (
        <div className="space-y-2">
          <h3 className="text-xs font-medium uppercase tracking-wide text-slate-500">
            Properties ({visibleCount})
          </h3>
          <div className="space-y-1 max-h-48 overflow-y-auto">
            {VOCAB_PROPERTIES.map((prop) => (
              <label
                key={prop.key}
                className="flex items-center gap-2 px-2 py-1.5 rounded-lg hover:bg-slate-50 text-sm text-slate-700 cursor-pointer"
              >
                <input
                  type="checkbox"
                  checked={config.visibleProperties.includes(prop.key)}
                  disabled={prop.isTitle}
                  onChange={() => toggleProperty(prop.key)}
                  className="rounded border-slate-300"
                />
                {prop.label}
              </label>
            ))}
          </div>
        </div>
      )}

      {(section === null || section === "filter") && (
        <div className="space-y-2">
          <h3 className="text-xs font-medium uppercase tracking-wide text-slate-500">
            Filter
          </h3>
          <FilterSection
            query={config.query}
            onChange={(query) =>
              onConfigChange((prev) => ({ ...prev, query }))
            }
          />
        </div>
      )}

      {(section === null || section === "sort") && (
        <div className="space-y-2">
          <h3 className="text-xs font-medium uppercase tracking-wide text-slate-500">
            Sort
          </h3>
          <div className="space-y-2">
            {config.sorts.map((rule, index) => (
              <div key={`${rule.field}-${index}`} className="flex gap-2">
                <select
                  value={rule.field}
                  onChange={(e) => {
                    const next = [...config.sorts];
                    next[index] = { ...rule, field: e.target.value };
                    updateSorts(next);
                  }}
                  className="flex-1 rounded-lg border border-slate-200 px-2 py-1.5 text-sm"
                >
                  {sortableProperties().map((p) => (
                    <option key={p.key} value={p.key}>
                      {p.label}
                    </option>
                  ))}
                </select>
                <select
                  value={rule.direction}
                  onChange={(e) => {
                    const next = [...config.sorts];
                    next[index] = {
                      ...rule,
                      direction: e.target.value as SortDirection,
                    };
                    updateSorts(next);
                  }}
                  className="rounded-lg border border-slate-200 px-2 py-1.5 text-sm"
                >
                  <option value="asc">Asc</option>
                  <option value="desc">Desc</option>
                </select>
                <button
                  type="button"
                  onClick={() =>
                    updateSorts(config.sorts.filter((_, i) => i !== index))
                  }
                  className="text-slate-400 hover:text-slate-600 px-1"
                >
                  ×
                </button>
              </div>
            ))}
            <button
              type="button"
              onClick={() =>
                updateSorts([
                  ...config.sorts,
                  { field: "word", direction: "asc" },
                ])
              }
              className="text-xs text-brand-600 hover:text-brand-700"
            >
              + Add sort
            </button>
          </div>
        </div>
      )}

      {(section === null || section === "group") && (
        <div className="space-y-2">
          <h3 className="text-xs font-medium uppercase tracking-wide text-slate-500">
            Group
          </h3>
          <select
            value={config.groupBy ?? ""}
            onChange={(e) =>
              onConfigChange((prev) => ({
                ...prev,
                groupBy: e.target.value || null,
              }))
            }
            className="w-full rounded-lg border border-slate-200 px-3 py-2 text-sm"
          >
            <option value="">None</option>
            {groupableProperties().map((p) => (
              <option key={p.key} value={p.key}>
                {p.label}
              </option>
            ))}
          </select>
        </div>
      )}
    </aside>
  );
}
