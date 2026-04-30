"use client";

import { useMemo } from "react";
import { useVocab } from "@/lib/storage";

export function TodayProgressWidget() {
  const { vocab, hydrated } = useVocab();

  const stats = useMemo(() => {
    const now = Date.now();
    let due = 0;
    let learned = 0;
    let total = 0;
    for (const item of vocab) {
      total += 1;
      if (item.learned) learned += 1;
      const next = item.mastery?.nextDue;
      if (typeof next === "number" && next <= now) due += 1;
    }
    return { due, learned, total };
  }, [vocab]);

  const learnedPct =
    stats.total > 0 ? Math.round((stats.learned / stats.total) * 100) : 0;

  return (
    <div className="glass-card glass-gloss rounded-2xl p-4">
      <h3 className="text-sm font-semibold text-slate-900 mb-3">
        Today&apos;s progress
      </h3>
      {!hydrated ? (
        <p className="text-xs text-slate-400">Loading…</p>
      ) : (
        <div className="grid grid-cols-3 gap-2">
          <Stat label="Due" value={stats.due} accent="text-amber-600" />
          <Stat label="Learned" value={stats.learned} accent="text-emerald-600" />
          <Stat label="Total" value={stats.total} accent="text-brand-700" />
        </div>
      )}
      {hydrated && stats.total > 0 && (
        <div className="mt-3">
          <div className="h-1.5 w-full rounded-full bg-white/60 overflow-hidden">
            <div
              className="h-full bg-gradient-to-r from-emerald-400 to-emerald-500"
              style={{ width: `${learnedPct}%` }}
            />
          </div>
          <p className="mt-1.5 text-[11px] text-slate-500">
            {learnedPct}% mastered
          </p>
        </div>
      )}
    </div>
  );
}

function Stat({
  label,
  value,
  accent,
}: {
  label: string;
  value: number;
  accent: string;
}) {
  return (
    <div className="rounded-xl bg-white/55 border border-white/50 px-2 py-2 text-center">
      <div className={`text-lg font-semibold ${accent}`}>{value}</div>
      <div className="text-[11px] text-slate-500">{label}</div>
    </div>
  );
}
