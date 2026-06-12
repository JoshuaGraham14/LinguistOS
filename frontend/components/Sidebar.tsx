"use client";

import {
  BookOpen,
  ChevronDown,
  ChevronRight,
  ChevronUp,
  Home,
  Layers,
  MoreHorizontal,
  Pencil,
  Plus,
  Settings,
  Table2,
  Trash2,
} from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useCallback, useEffect, useLayoutEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { Modal } from "@/components/Modal";
import { useSidebar } from "@/components/ResizableSidebar";
import { cn } from "@/lib/cn";
import { useWorkspaces } from "@/lib/storage";
import type { LanguageCode } from "@/lib/types";

type NavItem = {
  href: string;
  label: string;
  icon: typeof Home;
};

const NAV_SECTIONS: { title: string; items: NavItem[] }[] = [
  {
    title: "Workspace",
    items: [
      { href: "/", label: "Dashboard", icon: Home },
      { href: "/vocab", label: "Vocabulary", icon: Table2 },
    ],
  },
  {
    title: "Learn",
    items: [
      { href: "/learn", label: "All modes", icon: BookOpen },
      { href: "/learn/flashcards", label: "Flashcards", icon: Layers },
      { href: "/learn/sentences", label: "Sentences", icon: Pencil },
    ],
  },
];

const LANGUAGE_OPTIONS: { value: LanguageCode; label: string; emoji: string }[] = [
  { value: "es", label: "Spanish", emoji: "🇪🇸" },
  { value: "fr", label: "French", emoji: "🇫🇷" },
  { value: "he", label: "Hebrew", emoji: "🇮🇱" },
];

const WORKSPACE_MENU_WIDTH = 176;

type WorkspaceActionMenu = { workspaceId: number; top: number; left: number };

function menuLeftForAnchor(anchorRight: number): number {
  if (typeof window === "undefined") {
    return Math.max(8, anchorRight - WORKSPACE_MENU_WIDTH);
  }
  return Math.max(
    8,
    Math.min(anchorRight - WORKSPACE_MENU_WIDTH, window.innerWidth - WORKSPACE_MENU_WIDTH - 8),
  );
}

function isActive(pathname: string, href: string): boolean {
  if (href === "/") return pathname === "/";
  if (href === "/learn") return pathname === "/learn";
  return pathname.startsWith(href);
}

function WorkspaceNameInput({
  value,
  onChange,
  onCommit,
  onCancel,
}: {
  value: string;
  onChange: (v: string) => void;
  onCommit: () => void;
  onCancel: () => void;
}) {
  const inputRef = useRef<HTMLInputElement>(null);
  useLayoutEffect(() => {
    const el = inputRef.current;
    if (!el) return;
    el.focus();
    el.select();
  }, []);
  return (
    <input
      ref={inputRef}
      value={value}
      onChange={(e) => onChange(e.target.value)}
      onClick={(e) => e.stopPropagation()}
      onKeyDown={(e) => {
        if (e.key === "Enter") {
          e.preventDefault();
          onCommit();
        }
        if (e.key === "Escape") {
          e.preventDefault();
          onCancel();
        }
      }}
      onBlur={() => {
        window.setTimeout(() => onCommit(), 0);
      }}
      className="min-w-0 flex-1 rounded-md border border-violet-200/80 bg-white px-2 py-1 text-sm outline-none focus:ring-2 focus:ring-violet-300/80"
    />
  );
}

function Logo({ collapsed }: { collapsed: boolean }) {
  return (
    <Link
      href="/"
      className="flex items-center gap-2.5 min-w-0 group/logo focus:outline-none"
      aria-label="Go to dashboard"
      title="Dashboard"
    >
      <div className="h-9 w-9 rounded-xl overflow-hidden flex items-center justify-center shrink-0 relative group-hover/logo:scale-105 transition">
        {/* eslint-disable-next-line @next/next/no-img-element */}
        <img
          src="/logo.png"
          alt="LinguistOS"
          className="h-full w-full object-contain"
        />
      </div>
      {!collapsed && (
        <div className="font-bold text-slate-900 leading-tight truncate">
          Linguist
          <span className="ml-0.5 bg-[linear-gradient(90deg,#22c55e_0%,#0ea5e9_35%,#8b5cf6_68%,#ef4444_100%)] bg-clip-text text-transparent">
            OS
          </span>
        </div>
      )}
    </Link>
  );
}

export function Sidebar() {
  const { collapsed } = useSidebar();
  const pathname = usePathname();
  const {
    workspaces,
    activeWorkspace,
    activeWorkspaceId,
    setActiveWorkspaceId,
    createWorkspace,
    renameWorkspace,
    deleteWorkspace,
  } = useWorkspaces();
  const [open, setOpen] = useState(false);
  const [createOpen, setCreateOpen] = useState(false);
  const [workspaceName, setWorkspaceName] = useState("");
  const [workspaceLanguage, setWorkspaceLanguage] = useState<LanguageCode>("es");
  const [workspaceError, setWorkspaceError] = useState<string | null>(null);
  const [actionMenu, setActionMenu] = useState<WorkspaceActionMenu | null>(null);
  const actionMenuRef = useRef<HTMLDivElement>(null);
  const [editingWorkspaceId, setEditingWorkspaceId] = useState<number | null>(null);
  const editingWorkspaceIdRef = useRef<number | null>(null);
  const [editDraft, setEditDraft] = useState("");
  const [deleteTarget, setDeleteTarget] = useState<{ id: number; name: string } | null>(
    null,
  );
  const dropdownRef = useRef<HTMLDivElement>(null);
  const closeFlyoutTimerRef = useRef<number | null>(null);

  const cancelInlineRename = useCallback(() => {
    editingWorkspaceIdRef.current = null;
    setEditingWorkspaceId(null);
    setEditDraft("");
  }, []);

  const commitInlineRename = useCallback(async () => {
    const wid = editingWorkspaceIdRef.current;
    if (wid === null) return;
    const target = workspaces.find((w) => w.id === wid);
    const next = editDraft.trim();
    if (!next) {
      cancelInlineRename();
      return;
    }
    if (target && target.name === next) {
      cancelInlineRename();
      return;
    }
    try {
      await renameWorkspace(wid, next);
      setWorkspaceError(null);
      cancelInlineRename();
    } catch (error) {
      setWorkspaceError(
        error instanceof Error ? error.message : "Could not rename workspace",
      );
    }
  }, [editDraft, workspaces, renameWorkspace, cancelInlineRename]);

  useEffect(() => {
    function handleClick(e: MouseEvent) {
      const t = e.target as Node;
      if (dropdownRef.current?.contains(t)) return;
      // Portal menus live outside the dropdown DOM subtree.
      if (actionMenuRef.current?.contains(t)) return;
      setOpen(false);
    }
    if (open) document.addEventListener("mousedown", handleClick);
    return () => document.removeEventListener("mousedown", handleClick);
  }, [open]);

  useEffect(() => {
    if (!actionMenu) return;
    function closeIfOutside(e: MouseEvent) {
      const t = e.target as Node;
      if (actionMenuRef.current?.contains(t)) return;
      setActionMenu(null);
    }
    function closeOnScroll() {
      setActionMenu(null);
    }
    document.addEventListener("mousedown", closeIfOutside);
    window.addEventListener("scroll", closeOnScroll, true);
    return () => {
      document.removeEventListener("mousedown", closeIfOutside);
      window.removeEventListener("scroll", closeOnScroll, true);
    };
  }, [actionMenu]);

  // Close dropdown automatically when sidebar collapses (panel can't show below it).
  useEffect(() => {
    if (collapsed) setOpen(false);
  }, [collapsed]);

  const [wsHovered, setWsHovered] = useState(false);

  const clearFlyoutCloseTimer = () => {
    if (closeFlyoutTimerRef.current !== null) {
      window.clearTimeout(closeFlyoutTimerRef.current);
      closeFlyoutTimerRef.current = null;
    }
  };

  const openWorkspaceFlyout = () => {
    clearFlyoutCloseTimer();
    setWsHovered(true);
  };

  const scheduleWorkspaceFlyoutClose = (force = false) => {
    if (!force && actionMenu) return;
    clearFlyoutCloseTimer();
    closeFlyoutTimerRef.current = window.setTimeout(() => {
      setWsHovered(false);
    }, 180);
  };

  useEffect(() => {
    setWsHovered(false);
    clearFlyoutCloseTimer();
  }, [collapsed]);

  useEffect(
    () => () => {
      clearFlyoutCloseTimer();
    },
    [],
  );

  const selectedLanguageOption =
    LANGUAGE_OPTIONS.find((opt) => opt.value === workspaceLanguage) ??
    LANGUAGE_OPTIONS[0];

  const openWorkspaceActionsMenu = (workspaceId: number, anchor: HTMLElement) => {
    const r = anchor.getBoundingClientRect();
    clearFlyoutCloseTimer();
    if (collapsed) setWsHovered(true);
    setActionMenu((prev) =>
      prev?.workspaceId === workspaceId
        ? null
        : {
            workspaceId,
            top: r.bottom + 4,
            left: menuLeftForAnchor(r.right),
          },
    );
  };

  const startInlineRename = (workspaceId: number) => {
    const w = workspaces.find((x) => x.id === workspaceId);
    if (!w) return;
    editingWorkspaceIdRef.current = workspaceId;
    setEditingWorkspaceId(workspaceId);
    setEditDraft(w.name);
    setActionMenu(null);
    // Do not close expanded/collapsed picker — user stays in the list while renaming.
  };

  const pickWorkspace = (workspaceId: number, closePicker: () => void) => {
    if (editingWorkspaceId !== null && editingWorkspaceId !== workspaceId) {
      cancelInlineRename();
    }
    setActiveWorkspaceId(workspaceId);
    setActionMenu(null);
    closePicker();
  };

  const workspaceList = (closePicker: () => void) =>
    workspaces.map((workspace) => {
      const isActiveRow = activeWorkspaceId === workspace.id;
      const isEditing = editingWorkspaceId === workspace.id;
      return (
        <div
          key={workspace.id}
          className={cn(
            "flex items-center gap-0.5 rounded-xl px-2 py-1.5 transition-colors",
            isActiveRow
              ? "bg-violet-50/70 ring-1 ring-inset ring-violet-300/45"
              : "hover:bg-white/55",
          )}
        >
          <button
            type="button"
            onClick={() => pickWorkspace(workspace.id, closePicker)}
            className={cn(
              "flex min-w-0 flex-1 items-center gap-2 rounded-lg px-1 py-0.5 text-left text-sm text-slate-800",
              !isEditing && "select-none",
            )}
          >
            <span className="shrink-0 text-base">{workspace.emojiOrFlag}</span>
            {isEditing ? (
              <WorkspaceNameInput
                value={editDraft}
                onChange={setEditDraft}
                onCommit={() => void commitInlineRename()}
                onCancel={cancelInlineRename}
              />
            ) : (
              <span
                className={cn(
                  "min-w-0 flex-1 truncate select-none",
                  isActiveRow ? "font-medium" : "font-normal",
                )}
              >
                {workspace.name}
              </span>
            )}
          </button>
          {!isEditing && (
            <>
              <button
                type="button"
                onClick={(e) => {
                  e.preventDefault();
                  e.stopPropagation();
                  openWorkspaceActionsMenu(workspace.id, e.currentTarget);
                }}
                className="inline-flex h-7 w-7 shrink-0 items-center justify-center rounded-md text-slate-500 hover:bg-white/80"
                aria-label={`More actions for ${workspace.name}`}
              >
                <MoreHorizontal className="h-4 w-4" />
              </button>
            </>
          )}
        </div>
      );
    });

  const actionMenuPortal =
    typeof document !== "undefined" &&
    actionMenu &&
    createPortal(
      <div
        ref={actionMenuRef}
        className="fixed z-[380] w-44 rounded-xl border border-white/80 bg-white shadow-glass-lg backdrop-blur-md"
        style={{ top: actionMenu.top, left: actionMenu.left }}
        onMouseEnter={() => {
          clearFlyoutCloseTimer();
          if (collapsed) setWsHovered(true);
        }}
        onMouseLeave={() => {
          if (collapsed) scheduleWorkspaceFlyoutClose(true);
        }}
      >
        <button
          type="button"
          onClick={() => startInlineRename(actionMenu.workspaceId)}
          className="flex w-full items-center gap-2 rounded-t-xl px-3 py-2.5 text-left text-sm text-slate-700 hover:bg-slate-50"
        >
          <Pencil className="h-3.5 w-3.5" strokeWidth={2} />
          Rename workspace
        </button>
        <button
          type="button"
          onClick={() => {
            const w = workspaces.find((x) => x.id === actionMenu.workspaceId);
            if (w) {
              setWorkspaceError(null);
              setDeleteTarget({ id: w.id, name: w.name });
            }
            setActionMenu(null);
          }}
          className="flex w-full items-center gap-2 rounded-b-xl px-3 py-2.5 text-left text-sm text-rose-600 hover:bg-rose-50"
        >
          <Trash2 className="h-3.5 w-3.5" />
          Delete workspace
        </button>
      </div>,
      document.body,
    );

  return (
    <aside
      className={cn(
        "glass-panel rounded-none h-full flex flex-col relative overflow-visible",
        collapsed ? "items-center" : "",
      )}
    >
      {actionMenuPortal}

      <div
        className={cn(
          "flex border-b border-white/40 shrink-0",
          collapsed
            ? "flex-col items-center gap-2 px-3 py-3"
            : "items-center gap-2 px-4 py-3",
        )}
      >
        <Logo collapsed={collapsed} />
      </div>

      {/* Workspace switcher */}
      <div
        className={cn(
          "border-b border-white/40 shrink-0 relative",
          collapsed ? "px-3 py-3 w-full flex justify-center" : "px-3 py-3",
        )}
        ref={dropdownRef}
        onMouseEnter={() => collapsed && openWorkspaceFlyout()}
        onMouseLeave={() => collapsed && scheduleWorkspaceFlyoutClose()}
      >
        <button
          type="button"
          onClick={() => !collapsed && setOpen((prev) => !prev)}
          className={cn(
            "glass-pill rounded-xl flex items-center hover:bg-white/70 transition text-left relative",
            collapsed
              ? "h-10 w-10 justify-center p-0"
              : "w-full p-2.5 gap-2.5",
          )}
          title={collapsed ? activeWorkspace?.name : undefined}
        >
          <div className="relative h-9 w-9 shrink-0">
            <div
              className={cn(
                "absolute inset-0 rounded-lg bg-white/70 border border-white/60 flex items-center justify-center shadow-glass-inset transition-all duration-200",
                collapsed ? "text-base" : "text-lg",
                collapsed && wsHovered ? "opacity-0 scale-75" : "opacity-100 scale-100",
              )}
            >
              {activeWorkspace?.emojiOrFlag ?? "🌐"}
            </div>
            {collapsed && (
              <div
                className={cn(
                  "absolute inset-0 rounded-lg bg-white/70 border border-white/60 flex items-center justify-center text-slate-600 shadow-glass-inset transition-all duration-200",
                  wsHovered ? "opacity-100 scale-100" : "opacity-0 scale-75",
                )}
              >
                <ChevronRight className="h-4 w-4" strokeWidth={2.25} />
              </div>
            )}
          </div>
          {!collapsed && (
            <>
              <div className="min-w-0 flex-1">
                <div className="text-[10px] uppercase tracking-wide text-slate-500 leading-tight">
                  Workspace
                </div>
                <div className="font-semibold text-sm text-slate-900 truncate">
                  {activeWorkspace?.name ?? "Loading..."}
                </div>
              </div>
              <div className="flex flex-col text-slate-400 shrink-0">
                <ChevronUp className="h-3 w-3 -mb-0.5" strokeWidth={2.5} />
                <ChevronDown className="h-3 w-3" strokeWidth={2.5} />
              </div>
            </>
          )}
        </button>

        {/* Collapsed-mode flyout */}
        {collapsed && (
          <div
            onMouseEnter={openWorkspaceFlyout}
            onMouseLeave={() => scheduleWorkspaceFlyoutClose()}
            className={cn(
              "absolute left-full top-0 mt-0 ml-2 rounded-xl p-2 z-[80] w-64 transition-all duration-200",
              "bg-white border border-slate-200/90 shadow-xl shadow-slate-900/12 backdrop-blur-sm",
              wsHovered
                ? "opacity-100 translate-x-0 scale-100 pointer-events-auto"
                : "opacity-0 translate-x-1 scale-95 pointer-events-none",
            )}
          >
            <div className="space-y-0.5 py-0.5">
              {workspaceList(() => setWsHovered(false))}
            </div>
            <div className="mt-2 border-t border-white/40 pt-2">
              <button
                type="button"
                onClick={() => {
                  setCreateOpen(true);
                  setWsHovered(false);
                }}
                className="flex w-full items-center gap-2 rounded-lg px-3 py-2 text-sm text-slate-700 hover:bg-white/60 transition"
              >
                <Plus className="h-4 w-4" />
                New workspace
              </button>
            </div>
          </div>
        )}

        {open && !collapsed && (
          <div className="absolute left-3 right-3 top-full z-50 mt-2 rounded-xl border border-slate-200/90 bg-white p-2 shadow-xl shadow-slate-900/12 backdrop-blur-sm">
            <div className="space-y-0.5 py-0.5">{workspaceList(() => setOpen(false))}</div>
            <div className="mt-2 border-t border-white/40 pt-2">
              <button
                type="button"
                onClick={() => {
                  setCreateOpen(true);
                  setOpen(false);
                }}
                className="flex w-full items-center gap-2 rounded-lg px-3 py-2 text-sm text-slate-700 hover:bg-white/60 transition"
              >
                <Plus className="h-4 w-4" />
                New workspace
              </button>
            </div>
          </div>
        )}
      </div>

      {/* Nav */}
      <nav
        className={cn(
          "flex-1 min-h-0 overflow-y-auto flex flex-col gap-4 py-3",
          collapsed ? "px-2 items-center" : "px-3 pr-1",
        )}
      >
        {NAV_SECTIONS.map((section) => (
          <div
            key={section.title}
            className={cn(
              "flex flex-col gap-1",
              collapsed ? "items-center w-full" : "",
            )}
          >
            {!collapsed && (
              <div className="px-2 text-[10px] font-semibold uppercase tracking-wide text-slate-500">
                {section.title}
              </div>
            )}
            {collapsed && (
              <div className="h-px w-6 bg-white/40 my-1" aria-hidden="true" />
            )}
            {section.items.map(({ href, label, icon: Icon }) => {
              const active = isActive(pathname, href);
              return (
                <Link
                  key={href}
                  href={href}
                  title={collapsed ? label : undefined}
                  className={cn(
                    "flex items-center transition",
                    collapsed
                      ? "h-10 w-10 rounded-xl justify-center"
                      : "gap-2.5 rounded-xl px-3 py-2 text-sm",
                    active
                      ? "bg-white/80 text-slate-900 font-medium shadow-glass border border-white/60"
                      : "text-slate-700 hover:bg-white/50",
                  )}
                >
                  <Icon
                    className={cn(
                      "h-4 w-4 shrink-0",
                      active ? "text-brand-600" : "text-slate-500",
                    )}
                    strokeWidth={1.75}
                  />
                  {!collapsed && <span className="truncate">{label}</span>}
                </Link>
              );
            })}
          </div>
        ))}
      </nav>

      {/* Profile chip */}
      <div
        className={cn(
          "border-t border-white/40 shrink-0",
          collapsed ? "p-3" : "p-3",
        )}
      >
        <Link
          href="/settings"
          title="Settings"
          className={cn(
            "flex items-center transition",
            collapsed
              ? "h-10 w-10 rounded-xl justify-center"
              : "gap-2.5 rounded-xl px-3 py-2 text-sm",
            isActive(pathname, "/settings")
              ? "bg-white/80 text-slate-900 font-medium shadow-glass border border-white/60"
              : "text-slate-700 hover:bg-white/50",
          )}
        >
          <Settings
            className={cn(
              "h-4 w-4 shrink-0",
              isActive(pathname, "/settings") ? "text-brand-600" : "text-slate-500",
            )}
            strokeWidth={1.75}
          />
          {!collapsed && (
            <span className="truncate">Settings</span>
          )}
        </Link>
      </div>

      <Modal
        open={createOpen}
        onClose={() => setCreateOpen(false)}
        title="Create workspace"
      >
        <form
          className="space-y-4"
          onSubmit={async (e) => {
            try {
              e.preventDefault();
              const name = workspaceName.trim();
              if (!name) return;
              const emoji = selectedLanguageOption.emoji;
              await createWorkspace({
                name,
                language: workspaceLanguage,
                emojiOrFlag: emoji,
              });
              setWorkspaceName("");
              setWorkspaceLanguage("es");
              setWorkspaceError(null);
              setCreateOpen(false);
            } catch (error) {
              setWorkspaceError(
                error instanceof Error ? error.message : "Could not create workspace",
              );
            }
          }}
        >
          <label className="block">
            <span className="text-sm font-medium text-slate-700">Workspace name</span>
            <input
              value={workspaceName}
              onChange={(e) => setWorkspaceName(e.target.value)}
              placeholder="e.g. Travel Spanish"
              className="mt-1 w-full rounded-xl border border-slate-200 px-4 py-2.5 focus:outline-none focus:ring-2 focus:ring-brand-400"
            />
          </label>
          <label className="block">
            <span className="text-sm font-medium text-slate-700">Language</span>
            <select
              value={workspaceLanguage}
              onChange={(e) => setWorkspaceLanguage(e.target.value as LanguageCode)}
              className="mt-1 w-full rounded-xl border border-slate-200 px-4 py-2.5 focus:outline-none focus:ring-2 focus:ring-brand-400"
            >
              {LANGUAGE_OPTIONS.map((option) => (
                <option key={option.value} value={option.value}>
                  {option.emoji} {option.label}
                </option>
              ))}
            </select>
          </label>
          {workspaceError && (
            <p className="text-sm text-rose-600">{workspaceError}</p>
          )}
          <div className="flex justify-end gap-2 pt-2">
            <button
              type="button"
              onClick={() => setCreateOpen(false)}
              className="px-4 py-2 rounded-xl text-slate-600 hover:bg-slate-100 transition"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={!workspaceName.trim()}
              className="px-5 py-2 rounded-xl bg-btn-purple text-white font-medium shadow-soft hover:brightness-110 disabled:opacity-50"
            >
              Create
            </button>
          </div>
        </form>
      </Modal>

      <Modal
        open={deleteTarget !== null}
        onClose={() => setDeleteTarget(null)}
        title="Delete workspace"
      >
        {deleteTarget && (
          <div className="space-y-4">
            <p className="text-sm text-slate-600">
              Delete{" "}
              <span className="font-semibold text-slate-900">{deleteTarget.name}</span>
              ? This cannot be undone.
            </p>
            {workspaceError && (
              <p className="text-sm text-rose-600">{workspaceError}</p>
            )}
            <div className="flex justify-end gap-2 pt-2">
              <button
                type="button"
                onClick={() => {
                  setDeleteTarget(null);
                  setWorkspaceError(null);
                }}
                className="rounded-xl px-4 py-2 text-slate-600 transition hover:bg-slate-100"
              >
                Cancel
              </button>
              <button
                type="button"
                onClick={async () => {
                  try {
                    await deleteWorkspace(deleteTarget.id);
                    setWorkspaceError(null);
                    setDeleteTarget(null);
                    setOpen(false);
                    setWsHovered(false);
                    setActionMenu(null);
                  } catch (error) {
                    setWorkspaceError(
                      error instanceof Error
                        ? error.message
                        : "Could not delete workspace",
                    );
                  }
                }}
                className="rounded-xl bg-rose-600 px-5 py-2 font-medium text-white shadow-soft hover:brightness-110"
              >
                Delete
              </button>
            </div>
          </div>
        )}
      </Modal>
    </aside>
  );
}
