"use client";

import { MoreHorizontal, Plus } from "lucide-react";
import { useState } from "react";
import { cn } from "@/lib/cn";
import type { SavedView } from "@/lib/types";
import {
  ContextMenu,
  ContextMenuItem,
  ContextMenuLink,
  ContextMenuSeparator,
} from "./ContextMenu";

type ViewMenuState = {
  kind: "view";
  viewId: number;
  x: number;
  y: number;
};

type EmptyMenuState = {
  kind: "empty";
  x: number;
  y: number;
};

type MenuState = ViewMenuState | EmptyMenuState | null;

export function ViewTabBar({
  views,
  activeViewId,
  onSelect,
  onCreate,
  onRename,
  onDuplicate,
  onDelete,
  onMenuOpen,
}: {
  views: SavedView[];
  activeViewId: number | null;
  onSelect: (viewId: number) => void;
  onCreate: () => void;
  onRename: (view: SavedView) => void;
  onDuplicate: (view: SavedView) => void;
  onDelete: (view: SavedView) => void;
  onMenuOpen?: () => void;
}) {
  const [menu, setMenu] = useState<MenuState>(null);

  const menuView =
    menu?.kind === "view"
      ? (views.find((v) => v.id === menu.viewId) ?? null)
      : null;

  function openViewMenu(viewId: number, x: number, y: number) {
    onMenuOpen?.();
    setMenu({ kind: "view", viewId, x, y });
  }

  function closeMenu() {
    setMenu(null);
  }

  return (
    <>
      <div
        className="flex items-center gap-1 min-h-10 flex-1"
        onContextMenu={(e) => {
          if ((e.target as HTMLElement).closest("[data-view-tab]")) return;
          e.preventDefault();
          onMenuOpen?.();
          setMenu({ kind: "empty", x: e.clientX, y: e.clientY });
        }}
      >
        {views.map((view) => (
          <div key={view.id} className="flex items-center group shrink-0">
            <button
              type="button"
              data-view-tab
              onClick={() => onSelect(view.id)}
              onContextMenu={(e) => {
                e.preventDefault();
                openViewMenu(view.id, e.clientX, e.clientY);
              }}
              className={cn(
                "inline-flex items-center gap-1.5 px-3 h-10 text-sm font-medium border-b-2 transition",
                activeViewId === view.id
                  ? "border-brand-500 text-brand-700"
                  : "border-transparent text-slate-500 hover:text-slate-700",
              )}
            >
              {view.icon && <span aria-hidden>{view.icon}</span>}
              {view.name}
            </button>
            <button
              type="button"
              onClick={(e) => openViewMenu(view.id, e.clientX, e.clientY)}
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
          className="inline-flex items-center justify-center h-10 w-10 text-slate-400 hover:text-slate-600 rounded-lg hover:bg-slate-50 shrink-0"
          title="Add view"
        >
          <Plus className="h-4 w-4" />
        </button>
      </div>

      <ContextMenu
        open={menu?.kind === "view" && menuView != null}
        x={menu?.kind === "view" ? menu.x : 0}
        y={menu?.kind === "view" ? menu.y : 0}
        onClose={closeMenu}
      >
        {menuView && (
          <>
            <ContextMenuLink
              href={`/learn/flashcards?view=${menuView.id}`}
              onClick={closeMenu}
            >
              Practice this view
            </ContextMenuLink>
            <ContextMenuSeparator />
            <ContextMenuItem
              onClick={() => {
                onRename(menuView);
                closeMenu();
              }}
            >
              Rename
            </ContextMenuItem>
            <ContextMenuItem
              onClick={() => {
                onDuplicate(menuView);
                closeMenu();
              }}
            >
              Duplicate
            </ContextMenuItem>
            <ContextMenuItem
              destructive
              disabled={views.length <= 1}
              title={
                views.length <= 1 ? "Cannot delete the last view" : undefined
              }
              onClick={() => {
                onDelete(menuView);
                closeMenu();
              }}
            >
              Delete
            </ContextMenuItem>
          </>
        )}
      </ContextMenu>

      <ContextMenu
        open={menu?.kind === "empty"}
        x={menu?.kind === "empty" ? menu.x : 0}
        y={menu?.kind === "empty" ? menu.y : 0}
        onClose={closeMenu}
      >
        <ContextMenuItem
          onClick={() => {
            onCreate();
            closeMenu();
          }}
        >
          New view
        </ContextMenuItem>
      </ContextMenu>
    </>
  );
}
