"use client";

import { Keyboard, Settings as SettingsIcon } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { cn } from "@/lib/cn";
import type { PracticeSettings, VocabTag } from "@/lib/types";

const TAGS: VocabTag[] = [
  "noun",
  "verb",
  "adjective",
  "adverb",
  "preposition",
  "other",
];

export function SettingsPopover({
  settings,
  onChange,
}: {
  settings: PracticeSettings;
  onChange: (next: PracticeSettings) => void;
}) {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    function handleClick(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) {
        setOpen(false);
      }
    }
    if (open) document.addEventListener("mousedown", handleClick);
    return () => document.removeEventListener("mousedown", handleClick);
  }, [open]);

  function toggleTag(tag: VocabTag) {
    const next = settings.tagFilter.includes(tag)
      ? settings.tagFilter.filter((t) => t !== tag)
      : [...settings.tagFilter, tag];
    onChange({ ...settings, tagFilter: next });
  }

  return (
    <div className="relative" ref={ref}>
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        className="inline-flex items-center gap-2 rounded-2xl bg-white shadow-card px-5 py-3 text-slate-700 font-medium hover:bg-slate-50 transition"
      >
        <SettingsIcon className="h-5 w-5" strokeWidth={1.75} />
        Settings
      </button>

      {open && (
        <div className="absolute right-0 top-full mt-2 w-80 rounded-2xl bg-white shadow-card p-5 z-50 space-y-5">
          <div>
            <label className="text-sm font-semibold text-slate-700">
              Practice Mode
            </label>
            <div className="mt-2 relative">
              <Keyboard className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-slate-400" />
              <select
                value={settings.mode}
                onChange={(e) =>
                  onChange({ ...settings, mode: e.target.value as PracticeSettings["mode"] })
                }
                className="w-full appearance-none rounded-xl border border-slate-200 bg-white pl-10 pr-4 py-2.5 text-slate-900 focus:outline-none focus:ring-2 focus:ring-brand-400"
              >
                <option value="typing">Typing</option>
                <option value="multiple-choice">Multiple choice</option>
              </select>
            </div>
          </div>

          <div className="flex items-center justify-between">
            <span className="text-sm text-slate-700">Inglés → Español</span>
            <button
              type="button"
              onClick={() =>
                onChange({
                  ...settings,
                  direction:
                    settings.direction === "en-to-es" ? "es-to-en" : "en-to-es",
                })
              }
              className={cn(
                "relative h-6 w-11 rounded-full transition",
                settings.direction === "es-to-en" ? "bg-brand-500" : "bg-slate-200",
              )}
              aria-label="Toggle direction"
            >
              <span
                className={cn(
                  "absolute top-0.5 h-5 w-5 rounded-full bg-white shadow transition",
                  settings.direction === "es-to-en" ? "left-5" : "left-0.5",
                )}
              />
            </button>
          </div>

          <div>
            <label className="text-sm font-semibold text-slate-700">
              Sentence Length
            </label>
            <select
              value={settings.sentenceLength}
              onChange={(e) =>
                onChange({
                  ...settings,
                  sentenceLength: e.target.value as PracticeSettings["sentenceLength"],
                })
              }
              className="mt-2 w-full appearance-none rounded-xl border border-slate-200 bg-white px-4 py-2.5 text-slate-900 focus:outline-none focus:ring-2 focus:ring-brand-400"
            >
              <option value="short">Short</option>
              <option value="medium">Medium</option>
              <option value="long">Long</option>
            </select>
          </div>

          <div>
            <div className="text-sm font-semibold text-slate-700 mb-2">
              Filter by tags
            </div>
            <div className="flex flex-wrap gap-2">
              {TAGS.map((tag) => (
                <button
                  type="button"
                  key={tag}
                  onClick={() => toggleTag(tag)}
                  className={cn(
                    "px-3 py-1.5 rounded-full text-xs border transition capitalize",
                    settings.tagFilter.includes(tag)
                      ? "bg-brand-100 border-brand-300 text-brand-700"
                      : "bg-white border-slate-200 text-slate-600 hover:bg-slate-50",
                  )}
                >
                  {tag}
                </button>
              ))}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
