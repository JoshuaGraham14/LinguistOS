"use client";

import {
  BookMarked,
  BookOpen,
  ChevronDown,
  ChevronUp,
  Home,
  Layers,
  PanelLeftClose,
  PanelLeftOpen,
  Pencil,
  Plus,
  Settings,
  Table2,
  User as UserIcon,
} from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useRef, useState } from "react";
import { Modal } from "@/components/Modal";
import { useSidebar } from "@/components/ResizableSidebar";
import { cn } from "@/lib/cn";
import { useProfile, useWorkspaces } from "@/lib/storage";
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
      { href: "/words", label: "Words", icon: BookMarked },
      { href: "/lexicon", label: "Lexicon", icon: Table2 },
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
  {
    title: "General",
    items: [{ href: "/settings", label: "Settings", icon: Settings }],
  },
];

const LANGUAGE_OPTIONS: { value: LanguageCode; label: string; emoji: string }[] = [
  { value: "es", label: "Spanish", emoji: "🇪🇸" },
  { value: "fr", label: "French", emoji: "🇫🇷" },
  { value: "he", label: "Hebrew", emoji: "🇮🇱" },
];

function isActive(pathname: string, href: string): boolean {
  if (href === "/") return pathname === "/";
  if (href === "/learn") return pathname === "/learn";
  return pathname.startsWith(href);
}

function Logo({ collapsed }: { collapsed: boolean }) {
  return (
    <Link
      href="/"
      className="flex items-center gap-2.5 min-w-0 group/logo focus:outline-none"
      aria-label="Go to dashboard"
      title="Dashboard"
    >
      <div className="h-9 w-9 rounded-xl overflow-hidden flex items-center justify-center shrink-0 relative shadow-glass border border-white/60 bg-white/40 group-hover/logo:scale-105 transition">
        {/* eslint-disable-next-line @next/next/no-img-element */}
        <img
          src="/logo.png"
          alt="LinguistOS"
          className="h-full w-full object-contain"
        />
      </div>
      {!collapsed && (
        <div className="font-bold text-slate-900 leading-tight truncate">
          Linguist<span className="text-brand-600">OS</span>
        </div>
      )}
    </Link>
  );
}

export function Sidebar() {
  const { collapsed, toggle } = useSidebar();
  const pathname = usePathname();
  const { profile, hydrated } = useProfile();
  const {
    workspaces,
    activeWorkspace,
    activeWorkspaceId,
    setActiveWorkspaceId,
    createWorkspace,
    renameWorkspace,
  } = useWorkspaces();
  const [open, setOpen] = useState(false);
  const [createOpen, setCreateOpen] = useState(false);
  const [renameOpen, setRenameOpen] = useState(false);
  const [workspaceName, setWorkspaceName] = useState("");
  const [workspaceLanguage, setWorkspaceLanguage] = useState<LanguageCode>("es");
  const [renameName, setRenameName] = useState("");
  const [workspaceError, setWorkspaceError] = useState<string | null>(null);
  const dropdownRef = useRef<HTMLDivElement>(null);

  const displayName =
    hydrated && profile.name.trim() ? profile.name.trim() : "Friend";

  useEffect(() => {
    function handleClick(e: MouseEvent) {
      if (dropdownRef.current && !dropdownRef.current.contains(e.target as Node)) {
        setOpen(false);
      }
    }
    if (open) document.addEventListener("mousedown", handleClick);
    return () => document.removeEventListener("mousedown", handleClick);
  }, [open]);

  useEffect(() => {
    if (activeWorkspace) setRenameName(activeWorkspace.name);
  }, [activeWorkspace]);

  // Close dropdown automatically when sidebar collapses (panel can't show below it).
  useEffect(() => {
    if (collapsed) setOpen(false);
  }, [collapsed]);

  const [wsHovered, setWsHovered] = useState(false);

  // Cancel hover state on collapse change so a stale flyout doesn't linger.
  useEffect(() => {
    setWsHovered(false);
  }, [collapsed]);

  const selectedLanguageOption =
    LANGUAGE_OPTIONS.find((opt) => opt.value === workspaceLanguage) ??
    LANGUAGE_OPTIONS[0];

  return (
    <aside
      className={cn(
        "glass-panel rounded-r-2xl h-full flex flex-col relative",
        collapsed ? "items-center" : "",
      )}
    >
      {/* Header: in collapsed mode the toggle sits above the logo. */}
      <div
        className={cn(
          "flex border-b border-white/40 shrink-0",
          collapsed
            ? "flex-col items-center gap-2 px-3 py-3"
            : "items-center gap-2 px-4 py-3 justify-between",
        )}
      >
        {collapsed && (
          <button
            type="button"
            onClick={toggle}
            className="h-8 w-8 rounded-lg flex items-center justify-center text-slate-500 hover:bg-white/60 hover:text-slate-700 transition shrink-0"
            aria-label="Expand sidebar"
            title="Expand sidebar"
          >
            <PanelLeftOpen className="h-4 w-4" />
          </button>
        )}
        <Logo collapsed={collapsed} />
        {!collapsed && (
          <button
            type="button"
            onClick={toggle}
            className="h-7 w-7 rounded-lg flex items-center justify-center text-slate-500 hover:bg-white/60 hover:text-slate-700 transition shrink-0"
            aria-label="Collapse sidebar"
            title="Collapse sidebar"
          >
            <PanelLeftClose className="h-4 w-4" />
          </button>
        )}
      </div>

      {/* Workspace switcher */}
      <div
        className={cn(
          "border-b border-white/40 shrink-0 relative",
          collapsed ? "px-3 py-3 w-full flex justify-center" : "px-3 py-3",
        )}
        ref={dropdownRef}
        onMouseEnter={() => collapsed && setWsHovered(true)}
        onMouseLeave={() => collapsed && setWsHovered(false)}
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
          <div
            className={cn(
              "rounded-lg bg-white/70 border border-white/60 flex items-center justify-center text-lg shadow-glass-inset shrink-0",
              collapsed ? "h-8 w-8 text-base" : "h-9 w-9",
            )}
          >
            {activeWorkspace?.emojiOrFlag ?? "🌐"}
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

        {/* Collapsed-mode flyout: shown on hover. Lists every workspace plus
            a "+ New workspace" action so the user can switch or create from
            the icon rail. Active workspace is visually highlighted. */}
        {collapsed && wsHovered && (
          <div className="absolute left-full top-2 ml-1 z-40 flex flex-col gap-1.5 glass-card-strong rounded-xl p-1.5">
            {workspaces.map((w) => {
              const active = w.id === activeWorkspaceId;
              return (
                <button
                  key={w.id}
                  type="button"
                  onClick={() => {
                    setActiveWorkspaceId(w.id);
                    setWsHovered(false);
                  }}
                  title={w.name}
                  aria-label={`Switch to ${w.name}`}
                  className={cn(
                    "h-9 w-9 rounded-lg border flex items-center justify-center text-lg shadow-glass-inset transition",
                    active
                      ? "bg-white border-brand-300 ring-2 ring-brand-200"
                      : "bg-white/70 border-white/60 hover:bg-white",
                  )}
                >
                  {w.emojiOrFlag}
                </button>
              );
            })}
            {workspaces.length > 0 && (
              <div className="h-px w-full bg-white/40 my-0.5" aria-hidden="true" />
            )}
            <button
              type="button"
              onClick={() => {
                setCreateOpen(true);
                setWsHovered(false);
              }}
              title="New workspace"
              aria-label="New workspace"
              className="h-9 w-9 rounded-lg bg-white/70 border border-white/60 flex items-center justify-center text-slate-600 hover:bg-white shadow-glass-inset transition"
            >
              <Plus className="h-4 w-4" strokeWidth={2.25} />
            </button>
          </div>
        )}

        {open && !collapsed && (
          <div className="glass-card-strong absolute left-3 right-3 top-full mt-2 rounded-xl p-2 z-50">
            <div className="max-h-64 overflow-auto">
              {workspaces.map((workspace) => (
                <button
                  key={workspace.id}
                  type="button"
                  onClick={() => {
                    setActiveWorkspaceId(workspace.id);
                    setOpen(false);
                  }}
                  className={cn(
                    "w-full flex items-center gap-2 rounded-lg px-3 py-2 text-left text-sm hover:bg-white/60 transition",
                    activeWorkspaceId === workspace.id &&
                      "bg-white/70 text-slate-900 font-medium",
                  )}
                >
                  <span className="text-base">{workspace.emojiOrFlag}</span>
                  <span className="truncate">{workspace.name}</span>
                </button>
              ))}
            </div>
            <div className="border-t border-white/40 mt-2 pt-2 space-y-1">
              <button
                type="button"
                onClick={() => {
                  setCreateOpen(true);
                  setOpen(false);
                }}
                className="w-full flex items-center gap-2 rounded-lg px-3 py-2 text-sm text-slate-700 hover:bg-white/60 transition"
              >
                <Plus className="h-4 w-4" />
                New workspace
              </button>
              <button
                type="button"
                onClick={() => {
                  setRenameOpen(true);
                  setOpen(false);
                }}
                disabled={!activeWorkspace}
                className="w-full flex items-center gap-2 rounded-lg px-3 py-2 text-sm text-slate-700 hover:bg-white/60 disabled:opacity-40 transition"
              >
                Rename workspace
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
          title={collapsed ? displayName : undefined}
          className={cn(
            "glass-pill rounded-xl flex items-center hover:bg-white/70 transition",
            collapsed ? "h-10 w-10 justify-center p-0" : "p-2.5 gap-2.5",
          )}
        >
          <div
            className={cn(
              "rounded-full bg-gradient-to-br from-fuchsia-500 to-purple-600 flex items-center justify-center text-white shadow-glass shrink-0",
              collapsed ? "h-8 w-8" : "h-9 w-9",
            )}
          >
            <UserIcon className="h-4 w-4" strokeWidth={2} />
          </div>
          {!collapsed && (
            <div className="min-w-0">
              <div className="font-semibold text-sm text-slate-900 leading-tight truncate">
                {displayName}
              </div>
              <div className="text-[11px] text-slate-500">Edit profile</div>
            </div>
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
        open={renameOpen}
        onClose={() => setRenameOpen(false)}
        title="Rename workspace"
      >
        <form
          className="space-y-4"
          onSubmit={async (e) => {
            try {
              e.preventDefault();
              if (!activeWorkspace) return;
              const name = renameName.trim();
              if (!name) return;
              await renameWorkspace(activeWorkspace.id, name);
              setWorkspaceError(null);
              setRenameOpen(false);
            } catch (error) {
              setWorkspaceError(
                error instanceof Error ? error.message : "Could not rename workspace",
              );
            }
          }}
        >
          <label className="block">
            <span className="text-sm font-medium text-slate-700">Workspace name</span>
            <input
              value={renameName}
              onChange={(e) => setRenameName(e.target.value)}
              className="mt-1 w-full rounded-xl border border-slate-200 px-4 py-2.5 focus:outline-none focus:ring-2 focus:ring-brand-400"
            />
          </label>
          {workspaceError && (
            <p className="text-sm text-rose-600">{workspaceError}</p>
          )}
          <div className="flex justify-end gap-2 pt-2">
            <button
              type="button"
              onClick={() => setRenameOpen(false)}
              className="px-4 py-2 rounded-xl text-slate-600 hover:bg-slate-100 transition"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={!renameName.trim()}
              className="px-5 py-2 rounded-xl bg-btn-purple text-white font-medium shadow-soft hover:brightness-110 disabled:opacity-50"
            >
              Save
            </button>
          </div>
        </form>
      </Modal>
    </aside>
  );
}
