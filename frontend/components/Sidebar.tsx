"use client";

import {
  BookMarked,
  BookOpen,
  ChevronDown,
  Home,
  Plus,
  Settings,
  User as UserIcon,
} from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useRef, useState } from "react";
import { Modal } from "@/components/Modal";
import { cn } from "@/lib/cn";
import { useProfile, useWorkspaces } from "@/lib/storage";
import type { LanguageCode } from "@/lib/types";

const NAV = [
  { href: "/", label: "Dashboard", icon: Home },
  { href: "/words", label: "Words", icon: BookMarked },
  { href: "/learn", label: "Learn", icon: BookOpen },
  { href: "/settings", label: "Settings", icon: Settings },
] as const;

const LANGUAGE_OPTIONS: { value: LanguageCode; label: string; emoji: string }[] = [
  { value: "es", label: "Spanish", emoji: "🇪🇸" },
  { value: "fr", label: "French", emoji: "🇫🇷" },
  { value: "he", label: "Hebrew", emoji: "🇮🇱" },
];

export function Sidebar() {
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
  const ref = useRef<HTMLDivElement>(null);

  const displayName =
    hydrated && profile.name.trim() ? profile.name.trim() : "Friend";

  useEffect(() => {
    function handleClick(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) {
        setOpen(false);
      }
    }
    if (open) document.addEventListener("mousedown", handleClick);
    return () => document.removeEventListener("mousedown", handleClick);
  }, [open]);

  useEffect(() => {
    if (activeWorkspace) setRenameName(activeWorkspace.name);
  }, [activeWorkspace]);

  const selectedLanguageOption =
    LANGUAGE_OPTIONS.find((opt) => opt.value === workspaceLanguage) ??
    LANGUAGE_OPTIONS[0];

  return (
    <aside className="w-64 shrink-0 flex flex-col gap-3">
      <div className="relative" ref={ref}>
        <button
          type="button"
          onClick={() => setOpen((prev) => !prev)}
          className="w-full rounded-2xl bg-white/80 backdrop-blur shadow-card p-4 flex items-center gap-3 hover:bg-white transition text-left"
        >
          <div className="h-10 w-10 rounded-xl bg-slate-100 flex items-center justify-center text-xl">
            {activeWorkspace?.emojiOrFlag ?? "🌐"}
          </div>
          <div className="min-w-0 flex-1">
            <div className="text-sm text-slate-500 leading-tight">Workspace</div>
            <div className="font-semibold text-slate-900 truncate">
              {activeWorkspace?.name ?? "Loading..."}
            </div>
          </div>
          <ChevronDown className="h-4 w-4 text-slate-400 shrink-0" />
        </button>

        {open && (
          <div className="absolute left-0 right-0 top-full mt-2 rounded-2xl bg-white shadow-card p-2 z-50 border border-slate-100">
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
                    "w-full flex items-center gap-2 rounded-xl px-3 py-2 text-left text-sm hover:bg-slate-50",
                    activeWorkspaceId === workspace.id &&
                      "bg-slate-100 text-slate-900 font-medium",
                  )}
                >
                  <span className="text-base">{workspace.emojiOrFlag}</span>
                  <span className="truncate">{workspace.name}</span>
                </button>
              ))}
            </div>
            <div className="border-t border-slate-100 mt-2 pt-2 space-y-1">
              <button
                type="button"
                onClick={() => {
                  setCreateOpen(true);
                  setOpen(false);
                }}
                className="w-full flex items-center gap-2 rounded-xl px-3 py-2 text-sm text-slate-700 hover:bg-slate-50"
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
                className="w-full flex items-center gap-2 rounded-xl px-3 py-2 text-sm text-slate-700 hover:bg-slate-50 disabled:opacity-40"
              >
                Rename workspace
              </button>
            </div>
          </div>
        )}
      </div>

      <nav className="flex flex-col gap-2">
        {NAV.map(({ href, label, icon: Icon }) => {
          const active =
            href === "/" ? pathname === "/" : pathname.startsWith(href);
          return (
            <Link
              key={href}
              href={href}
              className={cn(
                "flex items-center gap-3 rounded-2xl bg-white/80 backdrop-blur px-5 py-3 shadow-soft text-slate-700 transition hover:bg-white hover:shadow-card",
                active && "bg-white shadow-card text-slate-900 font-medium",
              )}
            >
              <Icon className="h-5 w-5 text-slate-500" strokeWidth={1.75} />
              <span>{label}</span>
            </Link>
          );
        })}
      </nav>

      <Link
        href="/settings"
        className="mt-auto rounded-2xl bg-white/80 backdrop-blur shadow-card p-3 flex items-center gap-3 hover:bg-white transition"
      >
        <div className="h-10 w-10 rounded-full bg-gradient-to-br from-fuchsia-500 to-purple-600 flex items-center justify-center text-white shadow-md">
          <UserIcon className="h-5 w-5" strokeWidth={2} />
        </div>
        <div className="min-w-0">
          <div className="font-semibold text-slate-900 leading-tight truncate">
            {displayName}
          </div>
          <div className="text-xs text-slate-500">Edit profile</div>
        </div>
      </Link>

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
