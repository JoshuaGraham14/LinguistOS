"use client";

import { Keyboard, Settings as SettingsIcon } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { cn } from "@/lib/cn";
import type {
  GrammaticalNumber,
  LexiconConstraint,
  Person,
  PracticeSettings,
  Tense,
  VocabTag,
} from "@/lib/types";

const TAGS: VocabTag[] = [
  "noun",
  "verb",
  "adjective",
  "adverb",
  "preposition",
  "other",
];

const TENSES: { value: Tense; label: string }[] = [
  { value: "present", label: "Present" },
  { value: "preterite", label: "Preterite" },
  { value: "imperfect", label: "Imperfect" },
  { value: "future", label: "Future" },
  { value: "conditional", label: "Conditional" },
  { value: "subjunctive", label: "Subjunctive" },
];

const PERSONS: { value: Person; label: string }[] = [
  { value: "1st", label: "1st (yo / nosotros)" },
  { value: "2nd", label: "2nd (tú / vosotros)" },
  { value: "3rd", label: "3rd (él / ellos)" },
];

const NUMBERS: { value: GrammaticalNumber; label: string }[] = [
  { value: "singular", label: "Singular" },
  { value: "plural", label: "Plural" },
];

const LEXICON_CONSTRAINTS: { value: LexiconConstraint; label: string }[] = [
  { value: "off", label: "Off (any vocabulary)" },
  { value: "known_only", label: "Only words I know" },
  { value: "known_plus_stretch", label: "Known + stretch words" },
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

          <div className="border-t border-slate-100 pt-4 space-y-3">
            <div className="text-sm font-semibold text-slate-700">
              Lexicon constraint
            </div>
            <select
              value={settings.lexiconConstraint}
              onChange={(e) =>
                onChange({
                  ...settings,
                  lexiconConstraint: e.target.value as LexiconConstraint,
                })
              }
              className="w-full appearance-none rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm text-slate-900 focus:outline-none focus:ring-2 focus:ring-brand-400"
            >
              {LEXICON_CONSTRAINTS.map((c) => (
                <option key={c.value} value={c.value}>
                  {c.label}
                </option>
              ))}
            </select>
            {settings.lexiconConstraint === "known_plus_stretch" && (
              <label className="block">
                <span className="text-xs uppercase tracking-wide text-slate-500">
                  Stretch words
                </span>
                <input
                  type="number"
                  min={0}
                  max={20}
                  value={settings.stretchCount}
                  onChange={(e) =>
                    onChange({
                      ...settings,
                      stretchCount: Math.max(
                        0,
                        Math.min(20, Number(e.target.value) || 0),
                      ),
                    })
                  }
                  className="mt-1 w-full appearance-none rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm text-slate-900 focus:outline-none focus:ring-2 focus:ring-brand-400"
                />
              </label>
            )}
          </div>

          <div className="border-t border-slate-100 pt-4 space-y-3">
            <div className="text-sm font-semibold text-slate-700">
              Generation constraints
            </div>
            <label className="block">
              <span className="text-xs uppercase tracking-wide text-slate-500">
                Tense
              </span>
              <select
                value={settings.tense}
                onChange={(e) =>
                  onChange({ ...settings, tense: e.target.value as Tense })
                }
                className="mt-1 w-full appearance-none rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm text-slate-900 focus:outline-none focus:ring-2 focus:ring-brand-400"
              >
                {TENSES.map((t) => (
                  <option key={t.value} value={t.value}>
                    {t.label}
                  </option>
                ))}
              </select>
            </label>
            <label className="block">
              <span className="text-xs uppercase tracking-wide text-slate-500">
                Person
              </span>
              <select
                value={settings.person}
                onChange={(e) =>
                  onChange({ ...settings, person: e.target.value as Person })
                }
                className="mt-1 w-full appearance-none rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm text-slate-900 focus:outline-none focus:ring-2 focus:ring-brand-400"
              >
                {PERSONS.map((p) => (
                  <option key={p.value} value={p.value}>
                    {p.label}
                  </option>
                ))}
              </select>
            </label>
            <label className="block">
              <span className="text-xs uppercase tracking-wide text-slate-500">
                Number
              </span>
              <select
                value={settings.number}
                onChange={(e) =>
                  onChange({
                    ...settings,
                    number: e.target.value as GrammaticalNumber,
                  })
                }
                className="mt-1 w-full appearance-none rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm text-slate-900 focus:outline-none focus:ring-2 focus:ring-brand-400"
              >
                {NUMBERS.map((n) => (
                  <option key={n.value} value={n.value}>
                    {n.label}
                  </option>
                ))}
              </select>
            </label>
          </div>
        </div>
      )}
    </div>
  );
}
