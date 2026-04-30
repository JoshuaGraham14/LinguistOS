"use client";

import Link from "next/link";
import { useMemo } from "react";
import { useVocab, formatWordDisplay, useProfile } from "@/lib/storage";

export function RecentlyCapturedWidget({ limit = 6 }: { limit?: number }) {
  const { vocab, hydrated } = useVocab();
  const { profile } = useProfile();

  const recent = useMemo(() => {
    return [...vocab]
      .sort((a, b) => (b.createdAt ?? 0) - (a.createdAt ?? 0))
      .slice(0, limit);
  }, [vocab, limit]);

  return (
    <div className="glass-card rounded-2xl p-4">
      <div className="flex items-center justify-between mb-3">
        <h3 className="text-sm font-semibold text-slate-900">Recently captured</h3>
        <Link
          href="/words"
          className="text-xs text-brand-700 hover:text-brand-600 transition"
        >
          View all
        </Link>
      </div>
      {!hydrated ? (
        <p className="text-xs text-slate-400">Loading…</p>
      ) : recent.length === 0 ? (
        <p className="text-xs text-slate-500">
          No words yet. Add your first below.
        </p>
      ) : (
        <ul className="flex flex-col gap-1.5">
          {recent.map((item) => {
            const { primary, secondary } = formatWordDisplay(
              item,
              profile.wordDisplayMode,
            );
            return (
              <li key={item.id}>
                <Link
                  href={`/?word_quick=${item.id}`}
                  className="flex items-center justify-between gap-2 rounded-xl px-3 py-2 hover:bg-white/60 transition"
                >
                  <span className="min-w-0 flex-1 truncate text-sm text-slate-800">
                    {primary}
                    {secondary && (
                      <span className="ml-1.5 text-slate-400 text-xs">
                        · {secondary}
                      </span>
                    )}
                  </span>
                  {item.glossPrimary && (
                    <span className="shrink-0 text-xs text-slate-500 truncate max-w-[40%]">
                      {item.glossPrimary}
                    </span>
                  )}
                </Link>
              </li>
            );
          })}
        </ul>
      )}
    </div>
  );
}
