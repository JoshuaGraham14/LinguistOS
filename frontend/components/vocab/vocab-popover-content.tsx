"use client";

import { cn } from "@/lib/cn";
import {
  EMPTY_QUERY,
  isEmptyLexiconQuery,
  type DueFilter,
  type LearnedFilter,
  type LexiconQuery,
  type StatusMatch,
} from "@/lib/lexicon-query";
import { Kanban, LayoutGrid, Table2 } from "lucide-react";
import type { LucideIcon } from "lucide-react";
import type { SavedViewLayout, SortDirection, SortRule } from "@/lib/types";
import {
  groupableProperties,
  sortableProperties,
  VOCAB_PROPERTIES,
} from "@/lib/vocab-properties";
import type { VocabViewConfig } from "@/lib/vocab-view";

const TAG_OPTIONS = [
  "noun",
  "verb",
  "adjective",
  "adverb",
  "preposition",
  "other",
] as const;

const POS_OPTIONS = ["noun", "verb", "adjective", "adverb", "preposition"];
const CEFR_OPTIONS = ["A1", "A2", "B1", "B2", "C1", "C2"];
const LAYOUT_OPTIONS: {
  value: SavedViewLayout;
  label: string;
  icon: LucideIcon;
}[] = [
  { value: "table", label: "Table", icon: Table2 },
  { value: "gallery", label: "Cards", icon: LayoutGrid },
  { value: "board", label: "Board", icon: Kanban },
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

function toggleInList<T extends string>(list: T[], value: T): T[] {
  if (list.includes(value)) return list.filter((v) => v !== value);
  return [...list, value];
}

export function FilterPopoverContent({
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
      {query.learned !== "any" && query.due !== "any" && (
        <div className="flex items-center gap-2 flex-wrap">
          <span className="text-xs uppercase tracking-wide text-slate-500 w-full">
            Learned / due match
          </span>
          {(
            [
              { value: "all" as StatusMatch, label: "All (AND)" },
              { value: "any" as StatusMatch, label: "Any (OR)" },
            ] as const
          ).map((opt) => (
            <button
              key={opt.value}
              type="button"
              onClick={() => onChange({ ...query, statusMatch: opt.value })}
              className={cn(
                "px-2.5 py-1 rounded-full text-xs border transition",
                query.statusMatch === opt.value
                  ? "bg-sky-100 border-sky-300 text-sky-700"
                  : "bg-white border-slate-200 text-slate-600 hover:bg-slate-50",
              )}
            >
              {opt.label}
            </button>
          ))}
        </div>
      )}
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

export function SortPopoverContent({
  sorts,
  onChange,
}: {
  sorts: SortRule[];
  onChange: (sorts: SortRule[]) => void;
}) {
  return (
    <div className="space-y-2">
      {sorts.map((rule, index) => (
        <div key={`${rule.field}-${index}`} className="flex gap-2">
          <select
            value={rule.field}
            onChange={(e) => {
              const next = [...sorts];
              next[index] = { ...rule, field: e.target.value };
              onChange(next);
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
              const next = [...sorts];
              next[index] = {
                ...rule,
                direction: e.target.value as SortDirection,
              };
              onChange(next);
            }}
            className="rounded-lg border border-slate-200 px-2 py-1.5 text-sm"
          >
            <option value="asc">Asc</option>
            <option value="desc">Desc</option>
          </select>
          <button
            type="button"
            onClick={() => onChange(sorts.filter((_, i) => i !== index))}
            className="text-slate-400 hover:text-slate-600 px-1"
          >
            ×
          </button>
        </div>
      ))}
      <button
        type="button"
        onClick={() =>
          onChange([...sorts, { field: "createdAt", direction: "desc" }])
        }
        className="text-xs text-brand-600 hover:text-brand-700"
      >
        + Add sort
      </button>
    </div>
  );
}

export function ViewOptionsPopoverContent({
  layout,
  config,
  onLayoutChange,
  onConfigChange,
}: {
  layout: SavedViewLayout;
  config: VocabViewConfig;
  onLayoutChange: (layout: SavedViewLayout) => void;
  onConfigChange: (updater: (prev: VocabViewConfig) => VocabViewConfig) => void;
}) {
  return (
    <div className="space-y-4">
      <div className="space-y-2">
        <span className="text-xs font-medium uppercase tracking-wide text-slate-500">
          Layout
        </span>
        <div className="flex flex-col gap-1">
          {LAYOUT_OPTIONS.map((opt) => {
            const Icon = opt.icon;
            return (
              <button
                key={opt.value}
                type="button"
                onClick={() => onLayoutChange(opt.value)}
                className={cn(
                  "flex items-center gap-2.5 text-left px-3 py-2 rounded-lg text-sm transition w-full",
                  layout === opt.value
                    ? "bg-brand-50 text-brand-700 font-medium"
                    : "text-slate-600 hover:bg-slate-50",
                )}
              >
                <Icon
                  className={cn(
                    "h-4 w-4 shrink-0",
                    layout === opt.value ? "text-brand-600" : "text-slate-500",
                  )}
                  strokeWidth={2}
                />
                {opt.label}
              </button>
            );
          })}
        </div>
      </div>
      <div className="space-y-2">
        <span className="text-xs font-medium uppercase tracking-wide text-slate-500">
          Group
        </span>
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
    </div>
  );
}
