"use client";

import {
  ArrowDownUp,
  BookOpen,
  Filter,
  Plus,
  Search,
  Settings2,
} from "lucide-react";
import { cn } from "@/lib/cn";
import type { ViewSaveStatus } from "@/lib/useDebouncedViewPatch";

export function VocabToolbar({
  search,
  onSearchChange,
  saveStatus,
  hasActiveFilters,
  hasActiveSort,
  settingsOpen,
  onToggleSettings,
  onOpenFilter,
  onOpenSort,
  flashcardsHref,
  onNew,
}: {
  search: string;
  onSearchChange: (value: string) => void;
  saveStatus: ViewSaveStatus;
  hasActiveFilters: boolean;
  hasActiveSort: boolean;
  settingsOpen: boolean;
  onToggleSettings: () => void;
  onOpenFilter: () => void;
  onOpenSort: () => void;
  flashcardsHref: string;
  onNew: () => void;
}) {
  return (
    <div className="flex items-center justify-between gap-3 flex-wrap">
      <div className="relative flex-1 min-w-[200px] max-w-md">
        <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-slate-400" />
        <input
          value={search}
          onChange={(e) => onSearchChange(e.target.value)}
          placeholder="Search words…"
          className="w-full rounded-xl bg-slate-50 border border-slate-200 pl-9 pr-3 py-2 text-sm text-slate-900 placeholder:text-slate-400 focus:outline-none focus:ring-2 focus:ring-brand-400 focus:bg-white"
        />
      </div>
      <div className="flex items-center gap-2 flex-wrap">
        {saveStatus === "saving" && (
          <span className="text-xs text-slate-400">Saving…</span>
        )}
        {saveStatus === "saved" && (
          <span className="text-xs text-emerald-600">Saved</span>
        )}
        {saveStatus === "error" && (
          <span className="text-xs text-rose-600">Save failed</span>
        )}
        <button
          type="button"
          onClick={onToggleSettings}
          className={cn(
            "inline-flex items-center gap-1.5 rounded-xl border px-3 py-2 text-sm transition",
            settingsOpen
              ? "bg-brand-50 border-brand-200 text-brand-700"
              : "bg-white border-slate-200 text-slate-600 hover:bg-slate-50",
          )}
        >
          <Settings2 className="h-4 w-4" />
          View
        </button>
        <button
          type="button"
          onClick={onOpenFilter}
          className={cn(
            "inline-flex items-center gap-1.5 rounded-xl border px-3 py-2 text-sm transition",
            hasActiveFilters
              ? "bg-amber-50 border-amber-200 text-amber-700"
              : "bg-white border-slate-200 text-slate-600 hover:bg-slate-50",
          )}
        >
          <Filter className="h-4 w-4" />
          Filter
        </button>
        <button
          type="button"
          onClick={onOpenSort}
          className={cn(
            "inline-flex items-center gap-1.5 rounded-xl border px-3 py-2 text-sm transition",
            hasActiveSort
              ? "bg-violet-50 border-violet-200 text-violet-700"
              : "bg-white border-slate-200 text-slate-600 hover:bg-slate-50",
          )}
        >
          <ArrowDownUp className="h-4 w-4" />
          Sort
        </button>
        <a
          href={flashcardsHref}
          className="inline-flex items-center gap-1.5 rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm text-slate-600 hover:bg-slate-50 transition"
        >
          <BookOpen className="h-4 w-4" />
          Flashcards
        </a>
        <button
          type="button"
          onClick={onNew}
          className="inline-flex items-center gap-1.5 rounded-xl bg-brand-500 text-white font-medium px-4 py-2 text-sm shadow-soft hover:bg-brand-600 transition"
        >
          <Plus className="h-4 w-4" strokeWidth={2.5} />
          New
        </button>
      </div>
    </div>
  );
}
