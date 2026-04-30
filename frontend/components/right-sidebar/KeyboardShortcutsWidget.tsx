"use client";

import { shortcutLabel } from "@/lib/platform";

const SHORTCUTS = [
  { keys: ["Space"], label: "Flip card" },
  { keys: ["←", "→"], label: "Previous / Next" },
  { keys: ["J"], label: "Didn't know" },
  { keys: ["K"], label: "Knew it" },
] as const;

export function KeyboardShortcutsWidget() {
  return (
    <div className="glass-card rounded-2xl p-4">
      <h3 className="text-sm font-semibold text-slate-900 mb-3">Shortcuts</h3>
      <ul className="flex flex-col gap-2">
        {SHORTCUTS.map((s) => (
          <li
            key={s.label}
            className="flex items-center justify-between text-xs text-slate-600"
          >
            <span>{s.label}</span>
            <span className="flex gap-1">
              {s.keys.map((k) => (
                <kbd
                  key={k}
                  className="px-1.5 py-0.5 rounded bg-white/70 border border-white/60 text-[10px] font-mono text-slate-700 shadow-glass-inset"
                >
                  {k}
                </kbd>
              ))}
            </span>
          </li>
        ))}
        <li className="flex items-center justify-between text-xs text-slate-600 pt-2 border-t border-white/50">
          <span>Quick capture</span>
          <kbd className="px-1.5 py-0.5 rounded bg-white/70 border border-white/60 text-[10px] font-mono text-slate-700 shadow-glass-inset">
            {shortcutLabel("k")}
          </kbd>
        </li>
      </ul>
    </div>
  );
}
