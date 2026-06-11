"use client";

import { Plus } from "lucide-react";
import { cn } from "@/lib/cn";
import type { SavedView } from "@/lib/types";

export function ViewTabBar({
  views,
  activeViewId,
  onSelect,
  onCreate,
}: {
  views: SavedView[];
  activeViewId: number | null;
  onSelect: (viewId: number) => void;
  onCreate: () => void;
}) {
  return (
    <div className="flex items-center gap-1 flex-wrap border-b border-slate-200 pb-0">
      {views.map((view) => (
        <button
          key={view.id}
          type="button"
          onClick={() => onSelect(view.id)}
          className={cn(
            "inline-flex items-center gap-1.5 px-3 py-2 text-sm font-medium rounded-t-lg border-b-2 -mb-px transition",
            activeViewId === view.id
              ? "border-brand-500 text-brand-700 bg-white"
              : "border-transparent text-slate-500 hover:text-slate-700 hover:bg-slate-50",
          )}
        >
          {view.icon && <span aria-hidden>{view.icon}</span>}
          {view.name}
        </button>
      ))}
      <button
        type="button"
        onClick={onCreate}
        className="inline-flex items-center gap-1 px-2 py-2 text-sm text-slate-400 hover:text-slate-600 rounded-lg hover:bg-slate-50"
        title="Add view"
      >
        <Plus className="h-4 w-4" />
      </button>
    </div>
  );
}
