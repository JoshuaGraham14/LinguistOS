"use client";

import {
  ArrowDownUp,
  Eye,
  Filter,
  LayoutGrid,
  Plus,
  Search,
} from "lucide-react";
import { useRef } from "react";
import { cn } from "@/lib/cn";
import type { ViewSaveStatus } from "@/lib/useDebouncedViewPatch";
import type { SavedViewLayout } from "@/lib/types";
import type { VocabViewConfig } from "@/lib/vocab-view";
import { VocabPopover } from "./VocabPopover";
import { PropertyVisibilityPopover } from "./PropertyVisibilityPopover";
import {
  FilterPopoverContent,
  SortPopoverContent,
  ViewOptionsPopoverContent,
} from "./vocab-popover-content";

export type VocabPopoverId = "filter" | "sort" | "fields" | "view" | null;

export function VocabDatabaseToolbar({
  search,
  onSearchChange,
  saveStatus,
  activePopover,
  onTogglePopover,
  hasActiveFilters,
  hasActiveSort,
  hasGroup,
  hasHiddenProperties,
  config,
  layout,
  onLayoutChange,
  onConfigChange,
  onNew,
}: {
  search: string;
  onSearchChange: (value: string) => void;
  saveStatus: ViewSaveStatus;
  activePopover: VocabPopoverId;
  onTogglePopover: (id: Exclude<VocabPopoverId, null>) => void;
  hasActiveFilters: boolean;
  hasActiveSort: boolean;
  hasGroup: boolean;
  hasHiddenProperties: boolean;
  config: VocabViewConfig;
  layout: SavedViewLayout;
  onLayoutChange: (layout: SavedViewLayout) => void;
  onConfigChange: (updater: (prev: VocabViewConfig) => VocabViewConfig) => void;
  onNew: () => void;
}) {
  const filterRef = useRef<HTMLButtonElement>(null);
  const sortRef = useRef<HTMLButtonElement>(null);
  const fieldsRef = useRef<HTMLButtonElement>(null);
  const viewRef = useRef<HTMLButtonElement>(null);

  return (
    <div className="flex items-center gap-2 flex-shrink-0 py-1 pl-2">
      {saveStatus === "saving" && (
        <span className="text-xs text-slate-400 mr-1">Saving…</span>
      )}
      {saveStatus === "saved" && (
        <span className="text-xs text-emerald-600 mr-1">Saved</span>
      )}
      {saveStatus === "error" && (
        <span className="text-xs text-rose-600 mr-1">Save failed</span>
      )}

      <button
        ref={filterRef}
        type="button"
        title="Filter"
        onClick={() => onTogglePopover("filter")}
        className={cn(
          "h-9 w-9 rounded-lg border flex items-center justify-center transition",
          activePopover === "filter" || hasActiveFilters
            ? "bg-amber-50 border-amber-200 text-amber-700"
            : "bg-white border-slate-200 text-slate-600 hover:bg-slate-50",
        )}
      >
        <Filter className="h-4 w-4" />
      </button>
      <button
        ref={sortRef}
        type="button"
        title="Sort"
        onClick={() => onTogglePopover("sort")}
        className={cn(
          "h-9 w-9 rounded-lg border flex items-center justify-center transition",
          activePopover === "sort" || hasActiveSort
            ? "bg-violet-50 border-violet-200 text-violet-700"
            : "bg-white border-slate-200 text-slate-600 hover:bg-slate-50",
        )}
      >
        <ArrowDownUp className="h-4 w-4" />
      </button>
      <button
        ref={fieldsRef}
        type="button"
        title="Property visibility"
        onClick={() => onTogglePopover("fields")}
        className={cn(
          "h-9 w-9 rounded-lg border flex items-center justify-center transition",
          activePopover === "fields" || hasHiddenProperties
            ? "bg-brand-50 border-brand-200 text-brand-700"
            : "bg-white border-slate-200 text-slate-600 hover:bg-slate-50",
        )}
      >
        <Eye className="h-4 w-4" />
      </button>
      <button
        ref={viewRef}
        type="button"
        title="View"
        onClick={() => onTogglePopover("view")}
        className={cn(
          "h-9 w-9 rounded-lg border flex items-center justify-center transition",
          activePopover === "view" || hasGroup
            ? "bg-slate-100 border-slate-300 text-slate-800"
            : "bg-white border-slate-200 text-slate-600 hover:bg-slate-50",
        )}
      >
        <LayoutGrid className="h-4 w-4" />
      </button>

      <div className="relative w-44 hidden sm:block">
        <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 h-3.5 w-3.5 text-slate-400" />
        <input
          value={search}
          onChange={(e) => onSearchChange(e.target.value)}
          placeholder="Search…"
          className="w-full h-9 rounded-lg bg-slate-50 border border-slate-200 pl-8 pr-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-400"
        />
      </div>

      <button
        type="button"
        onClick={onNew}
        className="inline-flex items-center gap-1.5 h-9 rounded-lg bg-brand-500 text-white font-medium px-3 text-sm shadow-soft hover:bg-brand-600 transition"
      >
        <Plus className="h-4 w-4" strokeWidth={2.5} />
        Word
      </button>

      <VocabPopover
        open={activePopover === "filter"}
        onClose={() => onTogglePopover("filter")}
        anchorRef={filterRef}
        title="Filter"
      >
        <FilterPopoverContent
          query={config.query}
          onChange={(query) => onConfigChange((prev) => ({ ...prev, query }))}
        />
      </VocabPopover>
      <VocabPopover
        open={activePopover === "sort"}
        onClose={() => onTogglePopover("sort")}
        anchorRef={sortRef}
        title="Sort"
      >
        <SortPopoverContent
          sorts={config.sorts}
          onChange={(sorts) => onConfigChange((prev) => ({ ...prev, sorts }))}
        />
      </VocabPopover>
      <VocabPopover
        open={activePopover === "fields"}
        onClose={() => onTogglePopover("fields")}
        anchorRef={fieldsRef}
        title="Property visibility"
        width={300}
      >
        <PropertyVisibilityPopover
          config={config}
          onConfigChange={onConfigChange}
        />
      </VocabPopover>
      <VocabPopover
        open={activePopover === "view"}
        onClose={() => onTogglePopover("view")}
        anchorRef={viewRef}
        title="View"
        width={280}
      >
        <ViewOptionsPopoverContent
          layout={layout}
          config={config}
          onLayoutChange={onLayoutChange}
          onConfigChange={onConfigChange}
        />
      </VocabPopover>
    </div>
  );
}
