"use client";

import { Settings as SettingsIcon, User as UserIcon } from "lucide-react";
import { cn } from "@/lib/cn";
import { usePracticeSettings, useProfile } from "@/lib/storage";
import type {
  GrammaticalNumber,
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

export default function SettingsPage() {
  const { settings, setSettings, hydrated } = usePracticeSettings();
  const { profile, setProfile, hydrated: profileHydrated } = useProfile();

  function update<K extends keyof PracticeSettings>(
    key: K,
    value: PracticeSettings[K],
  ) {
    setSettings({ ...settings, [key]: value });
  }

  function toggleTag(tag: VocabTag) {
    const next = settings.tagFilter.includes(tag)
      ? settings.tagFilter.filter((t) => t !== tag)
      : [...settings.tagFilter, tag];
    update("tagFilter", next);
  }

  return (
    <div className="space-y-6 max-w-2xl">
      <header className="flex items-center gap-4">
        <div className="h-12 w-12 rounded-2xl bg-gradient-to-br from-fuchsia-500 to-purple-600 flex items-center justify-center shadow-md">
          <SettingsIcon className="h-6 w-6 text-white" strokeWidth={2} />
        </div>
        <div>
          <h1 className="text-3xl font-bold text-slate-900">Settings</h1>
          <p className="text-slate-500 mt-0.5">
            Practice preferences. Same controls available from the popover on
            the practice page.
          </p>
        </div>
      </header>

      <div className="rounded-2xl bg-white/80 backdrop-blur shadow-card p-6 space-y-2">
        <label className="flex items-center gap-2 text-sm font-semibold text-slate-700">
          <UserIcon className="h-4 w-4" strokeWidth={2} />
          Display name
        </label>
        <input
          value={profileHydrated ? profile.name : ""}
          onChange={(e) => setProfile({ ...profile, name: e.target.value })}
          placeholder="e.g. Josh"
          disabled={!profileHydrated}
          className="w-full rounded-xl border border-slate-200 bg-white px-4 py-2.5 text-slate-900 placeholder:text-slate-400 focus:outline-none focus:ring-2 focus:ring-brand-400 disabled:bg-slate-50"
        />
        <p className="text-xs text-slate-500">
          Shown on the dashboard and sidebar. Stored locally.
        </p>
      </div>

      {!hydrated ? (
        <div className="rounded-2xl bg-white/80 shadow-card p-12 text-center text-slate-400">
          Loading…
        </div>
      ) : (
        <div className="rounded-2xl bg-white/80 backdrop-blur shadow-card p-6 space-y-6">
          <section className="space-y-2">
            <label className="block text-sm font-semibold text-slate-700">
              Practice Mode
            </label>
            <select
              value={settings.mode}
              onChange={(e) =>
                update("mode", e.target.value as PracticeSettings["mode"])
              }
              className="w-full appearance-none rounded-xl border border-slate-200 bg-white px-4 py-2.5 text-slate-900 focus:outline-none focus:ring-2 focus:ring-brand-400"
            >
              <option value="typing">Typing</option>
              <option value="multiple-choice">Multiple choice</option>
            </select>
          </section>

          <section className="flex items-center justify-between">
            <span className="text-sm font-semibold text-slate-700">
              Translate from English to Spanish
            </span>
            <button
              type="button"
              onClick={() =>
                update(
                  "direction",
                  settings.direction === "en-to-es" ? "es-to-en" : "en-to-es",
                )
              }
              className={cn(
                "relative h-6 w-11 rounded-full transition",
                settings.direction === "en-to-es"
                  ? "bg-brand-500"
                  : "bg-slate-200",
              )}
              aria-label="Toggle direction"
            >
              <span
                className={cn(
                  "absolute top-0.5 h-5 w-5 rounded-full bg-white shadow transition",
                  settings.direction === "en-to-es" ? "left-5" : "left-0.5",
                )}
              />
            </button>
          </section>

          <section className="space-y-2">
            <label className="block text-sm font-semibold text-slate-700">
              Sentence Length
            </label>
            <select
              value={settings.sentenceLength}
              onChange={(e) =>
                update(
                  "sentenceLength",
                  e.target.value as PracticeSettings["sentenceLength"],
                )
              }
              className="w-full appearance-none rounded-xl border border-slate-200 bg-white px-4 py-2.5 text-slate-900 focus:outline-none focus:ring-2 focus:ring-brand-400"
            >
              <option value="short">Short</option>
              <option value="medium">Medium</option>
              <option value="long">Long</option>
            </select>
          </section>

          <section>
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
                    "px-3 py-1.5 rounded-full text-sm border transition capitalize",
                    settings.tagFilter.includes(tag)
                      ? "bg-brand-100 border-brand-300 text-brand-700"
                      : "bg-white border-slate-200 text-slate-600 hover:bg-slate-50",
                  )}
                >
                  {tag}
                </button>
              ))}
            </div>
          </section>

          <section className="border-t border-slate-100 pt-6 grid grid-cols-1 sm:grid-cols-3 gap-3">
            <label className="block">
              <span className="text-xs uppercase tracking-wide text-slate-500">
                Tense
              </span>
              <select
                value={settings.tense}
                onChange={(e) => update("tense", e.target.value as Tense)}
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
                onChange={(e) => update("person", e.target.value as Person)}
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
                  update("number", e.target.value as GrammaticalNumber)
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
          </section>
        </div>
      )}
    </div>
  );
}
