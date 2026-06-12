"use client";

import {
  Bell,
  ChevronLeft,
  ChevronRight,
  PanelLeftClose,
  PanelLeftOpen,
  Plus,
} from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useMemo, useRef, useState } from "react";
import { cn } from "@/lib/cn";
import { formatWordDisplay, useProfile, useVocab } from "@/lib/storage";
import { useAppHistory } from "./AppHistoryContext";
import { useQuickCapture } from "./QuickCaptureContext";

function initialsFromName(name: string) {
  const parts = name.trim().split(/\s+/).filter(Boolean);
  if (parts.length >= 2) {
    return (parts[0]![0]! + parts[1]![0]!).toUpperCase();
  }
  if (parts.length === 1 && parts[0]!.length >= 2) {
    return parts[0]!.slice(0, 2).toUpperCase();
  }
  return parts[0]?.[0]?.toUpperCase() ?? "?";
}

function titleForPath(pathname: string): string {
  if (pathname === "/") return "Dashboard";
  if (pathname === "/vocab") return "Vocabulary";
  if (pathname === "/words" || pathname === "/lexicon") return "Vocabulary";
  if (pathname === "/learn") return "All modes";
  if (pathname.startsWith("/learn/flashcards")) return "Flashcards";
  if (pathname.startsWith("/learn/sentences")) return "Sentences";
  if (pathname.startsWith("/settings")) return "Settings";
  const m = pathname.match(/^\/words\/(\d+)$/);
  if (m) return "Word";
  return "LinguistOS";
}

export function AppTopBar({
  leftCollapsed,
  onToggleLeft,
}: {
  leftCollapsed: boolean;
  onToggleLeft: () => void;
}) {
  const pathname = usePathname();
  const { canBack, canForward, goBack, goForward } = useAppHistory();
  const { openCapture } = useQuickCapture();
  const { profile, hydrated } = useProfile();
  const { vocab } = useVocab();

  const [notifOpen, setNotifOpen] = useState(false);
  const notifRef = useRef<HTMLDivElement>(null);

  const [wordQuick, setWordQuick] = useState<string | null>(null);
  const wordIdMatch = pathname.match(/^\/words\/(\d+)$/);
  const wordId = wordIdMatch ? Number(wordIdMatch[1]) : NaN;

  const item = useMemo(
    () => (Number.isFinite(wordId) ? vocab.find((v) => v.id === wordId) : undefined),
    [vocab, wordId],
  );

  const displayName =
    hydrated && profile.name.trim() ? profile.name.trim() : "Friend";

  const primaryTitle = useMemo(() => {
    if (wordIdMatch && item) {
      const d = formatWordDisplay(item, profile.wordDisplayMode);
      return d.secondary ? `${d.primary} (${d.secondary})` : d.primary;
    }
    return titleForPath(pathname);
  }, [wordIdMatch, item, profile.wordDisplayMode, pathname]);

  useEffect(() => {
    if (typeof window === "undefined") return;
    setWordQuick(new URLSearchParams(window.location.search).get("word_quick"));
  }, [pathname]);

  useEffect(() => {
    if (!notifOpen) return;
    function handlePointerDown(e: MouseEvent) {
      const el = notifRef.current;
      if (el && !el.contains(e.target as Node)) {
        setNotifOpen(false);
      }
    }
    document.addEventListener("mousedown", handlePointerDown);
    return () => document.removeEventListener("mousedown", handlePointerDown);
  }, [notifOpen]);

  return (
    <header
      className={cn(
        "shrink-0 h-14 flex items-center gap-3 px-2 lg:px-3",
        "border-b border-white/50 bg-white/70 backdrop-blur-glass-strong rounded-none",
      )}
    >
      <div className="flex items-center gap-1 shrink-0">
        <button
          type="button"
          onClick={onToggleLeft}
          className={cn(
            "hidden md:inline-flex h-9 w-9 rounded-xl items-center justify-center border border-transparent",
            "text-slate-600 hover:bg-white/60 hover:text-slate-800",
            "focus:outline-none focus-visible:ring-2 focus-visible:ring-brand-500 transition",
          )}
          aria-label={leftCollapsed ? "Expand left sidebar" : "Collapse left sidebar"}
          title={leftCollapsed ? "Expand left sidebar" : "Collapse left sidebar"}
        >
          {leftCollapsed ? (
            <PanelLeftOpen className="h-4 w-4" />
          ) : (
            <PanelLeftClose className="h-4 w-4" />
          )}
        </button>
        <button
          type="button"
          onClick={goBack}
          disabled={!canBack}
          className={cn(
            "rounded-xl p-2 border border-transparent transition",
            canBack
              ? "text-slate-800 hover:bg-white/60"
              : "text-slate-400 cursor-not-allowed opacity-70",
            "focus:outline-none focus-visible:ring-2 focus-visible:ring-brand-500",
          )}
          aria-label="Back"
        >
          <ChevronLeft className="h-5 w-5" strokeWidth={2} />
        </button>
        <button
          type="button"
          onClick={goForward}
          disabled={!canForward}
          className={cn(
            "rounded-xl p-2 border border-transparent transition",
            canForward
              ? "text-slate-800 hover:bg-white/60"
              : "text-slate-400 cursor-not-allowed opacity-70",
            "focus:outline-none focus-visible:ring-2 focus-visible:ring-brand-500",
          )}
          aria-label="Forward"
        >
          <ChevronRight className="h-5 w-5" strokeWidth={2} />
        </button>
      </div>

      <div className="flex-1 min-w-0 flex flex-col justify-center">
        <h1 className="text-sm font-semibold text-slate-900 truncate">{primaryTitle}</h1>
        {wordQuick ? (
          <span className="text-[11px] text-slate-500 truncate">Quick view</span>
        ) : null}
      </div>

      <div className="flex items-center gap-1 shrink-0">
        <button
          type="button"
          onClick={openCapture}
          className={cn(
            "inline-flex items-center gap-2 rounded-xl px-3 py-2 border border-white/70",
            "bg-gradient-to-br from-emerald-200/90 via-sky-200/90 to-violet-200/90 text-slate-800",
            "hover:brightness-105 hover:-translate-y-0.5 shadow-glass transition glass-gloss",
            "focus:outline-none focus-visible:ring-2 focus-visible:ring-brand-500 relative overflow-hidden",
          )}
          aria-label="Quick add a word"
        >
          <Plus className="h-4 w-4 relative" strokeWidth={2.5} />
          <span className="relative text-sm font-medium">Quick add</span>
        </button>

        <div className="relative" ref={notifRef}>
          <button
            type="button"
            onClick={() => setNotifOpen((o) => !o)}
            aria-expanded={notifOpen}
            aria-haspopup="true"
            className={cn(
              "rounded-xl p-2 text-slate-800 hover:bg-white/60 border border-transparent",
              "focus:outline-none focus-visible:ring-2 focus-visible:ring-brand-500",
            )}
            aria-label="Notifications"
          >
            <Bell className="h-5 w-5" strokeWidth={2} />
          </button>
          {notifOpen ? (
            <div
              className={cn(
                "absolute right-0 top-full mt-1 z-50 w-56 py-3 px-3",
                "bg-white/95 backdrop-blur-glass border border-white/60 shadow-glass-lg rounded-xl text-sm text-slate-600",
              )}
            >
              No notifications
            </div>
          ) : null}
        </div>

        <div className="w-px h-6 bg-white/50 shrink-0 mx-1" aria-hidden="true" />

        <Link
          href="/settings"
          className={cn(
            "rounded-xl flex items-center gap-2 pl-1 pr-2 py-1.5",
            "hover:bg-white/60 border border-transparent",
            "focus:outline-none focus-visible:ring-2 focus-visible:ring-brand-500",
          )}
        >
          <span
            className={cn(
              "h-8 w-8 shrink-0 flex items-center justify-center",
              "bg-gradient-to-br from-fuchsia-500 to-purple-600 text-white text-xs font-semibold rounded-full",
            )}
            aria-hidden="true"
          >
            {initialsFromName(displayName)}
          </span>
          <span className="hidden sm:flex flex-col min-w-0 text-left">
            <span className="text-sm font-semibold text-slate-900 truncate max-w-[140px]">
              {displayName}
            </span>
            <span className="text-[11px] text-slate-500">Profile</span>
          </span>
        </Link>
      </div>
    </header>
  );
}
