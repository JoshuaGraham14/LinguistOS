"use client";

import { MoreHorizontal, Plus } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { cn } from "@/lib/cn";
import type { SavedView } from "@/lib/types";

export function ViewTabBar({
  views,
  activeViewId,
  onSelect,
  onCreate,
  onRename,
  onDuplicate,
  onDelete,
}: {
  views: SavedView[];
  activeViewId: number | null;
  onSelect: (viewId: number) => void;
  onCreate: () => void;
  onRename: (view: SavedView) => void;
  onDuplicate: (view: SavedView) => void;
  onDelete: (view: SavedView) => void;
}) {
  const [menuViewId, setMenuViewId] = useState<number | null>(null);
  const [menuPos, setMenuPos] = useState({ top: 0, left: 0 });
  const menuRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (menuViewId == null) return;
    function onClick(e: MouseEvent) {
      if (menuRef.current?.contains(e.target as Node)) return;
      setMenuViewId(null);
    }
    document.addEventListener("mousedown", onClick);
    return () => document.removeEventListener("mousedown", onClick);
  }, [menuViewId]);

  const menuView = views.find((v) => v.id === menuViewId) ?? null;

  function openMenu(viewId: number, el: HTMLElement) {
    const rect = el.getBoundingClientRect();
    setMenuPos({ top: rect.bottom + 4, left: rect.left });
    setMenuViewId(viewId);
  }

  return (
    <div className="flex items-center gap-1 flex-wrap pb-0">
      {views.map((view) => (
        <div key={view.id} className="flex items-center group">
          <button
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
          <button
            type="button"
            onClick={(e) => openMenu(view.id, e.currentTarget)}
            className="h-7 w-7 rounded-lg text-slate-400 hover:text-slate-600 hover:bg-slate-100 opacity-0 group-hover:opacity-100 focus:opacity-100 transition"
            aria-label={`Options for ${view.name}`}
          >
            <MoreHorizontal className="h-4 w-4 mx-auto" />
          </button>
        </div>
      ))}
      <button
        type="button"
        onClick={onCreate}
        className="inline-flex items-center gap-1 px-2 py-2 text-sm text-slate-400 hover:text-slate-600 rounded-lg hover:bg-slate-50"
        title="Add view"
      >
        <Plus className="h-4 w-4" />
      </button>

      {menuView &&
        typeof document !== "undefined" &&
        createPortal(
          <div
            ref={menuRef}
            className="fixed z-[360] min-w-[160px] rounded-xl border border-slate-200 bg-white shadow-lg py-1"
            style={{ top: menuPos.top, left: menuPos.left }}
          >
            <button
              type="button"
              className="w-full text-left px-3 py-2 text-sm text-slate-700 hover:bg-slate-50"
              onClick={() => {
                onRename(menuView);
                setMenuViewId(null);
              }}
            >
              Rename
            </button>
            <button
              type="button"
              className="w-full text-left px-3 py-2 text-sm text-slate-700 hover:bg-slate-50"
              onClick={() => {
                onDuplicate(menuView);
                setMenuViewId(null);
              }}
            >
              Duplicate
            </button>
            <button
              type="button"
              className="w-full text-left px-3 py-2 text-sm text-rose-600 hover:bg-rose-50 disabled:opacity-40"
              disabled={views.length <= 1}
              onClick={() => {
                onDelete(menuView);
                setMenuViewId(null);
              }}
            >
              Delete
            </button>
          </div>,
          document.body,
        )}
    </div>
  );
}
