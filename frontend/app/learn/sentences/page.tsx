"use client";

import {
  ArrowLeft,
  ChevronLeft,
  ChevronRight,
  Loader2,
  RefreshCw,
  Sparkles,
  Volume2,
} from "lucide-react";
import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import { generateOrMock } from "@/lib/api";
import { cn } from "@/lib/cn";
import { useVocab } from "@/lib/storage";
import type { SentenceCandidate } from "@/lib/types";

const TENSES = [
  { value: "present", label: "Present" },
  { value: "preterite", label: "Preterite" },
  { value: "imperfect", label: "Imperfect" },
  { value: "future", label: "Future" },
  { value: "conditional", label: "Conditional" },
  { value: "subjunctive", label: "Subjunctive" },
];

const PERSONS = [
  { value: "1st", label: "1st (yo / nosotros)" },
  { value: "2nd", label: "2nd (tú / vosotros)" },
  { value: "3rd", label: "3rd (él / ellos)" },
];

const NUMBERS = [
  { value: "singular", label: "Singular" },
  { value: "plural", label: "Plural" },
];

function normalize(s: string) {
  return s
    .trim()
    .toLowerCase()
    .replace(/[.,!?¿¡]/g, "")
    .replace(/\s+/g, " ");
}

export default function SentencePracticePage() {
  const { vocab, hydrated } = useVocab();
  const [wordIndex, setWordIndex] = useState(0);
  const [tense, setTense] = useState("present");
  const [person, setPerson] = useState("3rd");
  const [number, setNumber] = useState("singular");

  const [candidate, setCandidate] = useState<SentenceCandidate | null>(null);
  const [allCandidates, setAllCandidates] = useState<SentenceCandidate[]>([]);
  const [generating, setGenerating] = useState(false);
  const [isMock, setIsMock] = useState(false);

  const [answer, setAnswer] = useState("");
  const [feedback, setFeedback] = useState<"correct" | "incorrect" | null>(null);

  const current = vocab[wordIndex];

  useEffect(() => {
    setCandidate(null);
    setAllCandidates([]);
    setAnswer("");
    setFeedback(null);
  }, [wordIndex, tense, person, number]);

  async function handleGenerate() {
    if (!current) return;
    setGenerating(true);
    setFeedback(null);
    setAnswer("");
    try {
      const res = await generateOrMock({
        word: current.word,
        translation: current.translation,
        tense,
        person,
        number,
        num_candidates: 3,
      });
      setAllCandidates(res.candidates);
      setCandidate(res.candidates[0] ?? null);
      setIsMock(Boolean(res.mock));
    } finally {
      setGenerating(false);
    }
  }

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!candidate || !candidate.translation) return;
    const ok = normalize(answer) === normalize(candidate.translation);
    setFeedback(ok ? "correct" : "incorrect");
  }

  function handleNext() {
    setAnswer("");
    setFeedback(null);
    handleGenerate();
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <Link
          href="/learn"
          className="inline-flex items-center gap-2 rounded-2xl bg-white shadow-card px-5 py-3 text-slate-700 font-medium hover:bg-slate-50 transition"
        >
          <ArrowLeft className="h-5 w-5" strokeWidth={1.75} />
          Back
        </Link>
        <h1 className="text-2xl font-bold text-slate-900">Sentence Practice</h1>
        <div className="w-[100px]" />
      </div>

      {!hydrated ? (
        <div className="rounded-2xl bg-white/80 shadow-card p-12 text-center text-slate-400">
          Loading…
        </div>
      ) : vocab.length === 0 ? (
        <div className="rounded-2xl bg-white/80 shadow-card p-12 text-center">
          <p className="text-slate-600">
            Add some words on the{" "}
            <Link href="/words" className="text-brand-600 underline">
              Words page
            </Link>{" "}
            first.
          </p>
        </div>
      ) : (
        <>
          <section className="rounded-2xl bg-white/80 backdrop-blur shadow-card p-6 flex items-center justify-between gap-4">
            <button
              type="button"
              onClick={() =>
                setWordIndex((i) => (i - 1 + vocab.length) % vocab.length)
              }
              className="h-10 w-10 rounded-xl bg-slate-100 text-slate-700 flex items-center justify-center hover:bg-slate-200 transition"
              aria-label="Previous word"
            >
              <ChevronLeft className="h-5 w-5" strokeWidth={2.5} />
            </button>

            <div className="flex-1 text-center">
              <div className="text-xs uppercase tracking-wide text-slate-500">
                Practicing word {wordIndex + 1} of {vocab.length}
              </div>
              <div className="text-3xl font-bold text-slate-900 mt-1">
                {current.word}
              </div>
              <div className="text-slate-500">{current.translation}</div>
            </div>

            <button
              type="button"
              onClick={() => setWordIndex((i) => (i + 1) % vocab.length)}
              className="h-10 w-10 rounded-xl bg-slate-100 text-slate-700 flex items-center justify-center hover:bg-slate-200 transition"
              aria-label="Next word"
            >
              <ChevronRight className="h-5 w-5" strokeWidth={2.5} />
            </button>
          </section>

          <section className="rounded-2xl bg-white/80 backdrop-blur shadow-card p-6 space-y-4">
            <div className="text-sm font-semibold text-slate-700 flex items-center gap-2">
              <Sparkles className="h-4 w-4 text-brand-500" strokeWidth={2} />
              Generation parameters
            </div>
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
              <ParamSelect
                label="Tense"
                value={tense}
                options={TENSES}
                onChange={setTense}
              />
              <ParamSelect
                label="Person"
                value={person}
                options={PERSONS}
                onChange={setPerson}
              />
              <ParamSelect
                label="Number"
                value={number}
                options={NUMBERS}
                onChange={setNumber}
              />
            </div>
            <button
              type="button"
              onClick={handleGenerate}
              disabled={generating}
              className="w-full rounded-xl bg-btn-purple text-white font-medium py-3 shadow-soft hover:brightness-110 disabled:opacity-60 disabled:cursor-not-allowed transition inline-flex items-center justify-center gap-2"
            >
              {generating ? (
                <>
                  <Loader2 className="h-4 w-4 animate-spin" />
                  Generating…
                </>
              ) : candidate ? (
                <>
                  <RefreshCw className="h-4 w-4" strokeWidth={2.5} />
                  Generate again
                </>
              ) : (
                <>
                  <Sparkles className="h-4 w-4" strokeWidth={2.5} />
                  Generate sentence
                </>
              )}
            </button>
          </section>

          {candidate && (
            <>
              <section className="rounded-3xl bg-white/90 backdrop-blur shadow-card p-12 min-h-[280px] relative flex flex-col items-center justify-center">
                {isMock && (
                  <div className="absolute top-4 right-4 px-3 py-1 rounded-full bg-amber-100 text-amber-700 text-xs font-medium">
                    Demo mode (no backend)
                  </div>
                )}
                <button
                  type="button"
                  className="absolute top-5 left-5 h-10 w-10 rounded-xl bg-blue-500 text-white flex items-center justify-center hover:bg-blue-600 transition"
                  aria-label="Play audio"
                >
                  <Volume2 className="h-5 w-5" strokeWidth={2} />
                </button>
                <div className="text-slate-500">Translate this sentence:</div>
                <div className="mt-3 text-3xl md:text-4xl font-bold text-slate-900 text-center">
                  {candidate.sentence}
                </div>
              </section>

              <form
                onSubmit={handleSubmit}
                className="rounded-2xl bg-white/80 backdrop-blur shadow-card p-6 flex flex-col gap-4"
              >
                <input
                  value={answer}
                  onChange={(e) => {
                    setAnswer(e.target.value);
                    setFeedback(null);
                  }}
                  placeholder="Type the English translation..."
                  className="w-full rounded-xl border border-slate-200 bg-white px-4 py-3 text-slate-900 placeholder:text-slate-400 focus:outline-none focus:ring-2 focus:ring-brand-400"
                />
                <div className="flex items-center justify-between gap-3">
                  <button
                    type="button"
                    onClick={handleNext}
                    className="text-sm text-slate-600 hover:text-slate-900 transition"
                  >
                    Skip → next sentence
                  </button>
                  <button
                    type="submit"
                    disabled={!answer.trim()}
                    className={cn(
                      "rounded-xl px-8 py-3 font-medium text-white transition",
                      answer.trim()
                        ? "bg-btn-purple hover:brightness-110 shadow-card"
                        : "bg-slate-300 cursor-not-allowed",
                    )}
                  >
                    Submit
                  </button>
                </div>
                {feedback && (
                  <div
                    className={cn(
                      "rounded-xl p-4 text-sm",
                      feedback === "correct"
                        ? "bg-emerald-50 text-emerald-700"
                        : "bg-rose-50 text-rose-700",
                    )}
                  >
                    {feedback === "correct" ? (
                      <span>¡Correcto!</span>
                    ) : (
                      <span>
                        Not quite. Expected:{" "}
                        <strong>{candidate.translation}</strong>
                      </span>
                    )}
                  </div>
                )}
              </form>

              {allCandidates.length > 1 && (
                <details className="rounded-2xl bg-white/60 backdrop-blur shadow-soft p-5">
                  <summary className="cursor-pointer text-sm font-semibold text-slate-700 list-none flex items-center justify-between">
                    <span>Other candidates ({allCandidates.length - 1})</span>
                    <span className="text-slate-400 text-xs">
                      thesis-mode inspector
                    </span>
                  </summary>
                  <ul className="mt-4 space-y-2">
                    {allCandidates.slice(1).map((c, i) => (
                      <li
                        key={i}
                        className="flex items-start justify-between gap-3 rounded-xl bg-white p-3 border border-slate-100"
                      >
                        <div>
                          <div className="text-slate-900">{c.sentence}</div>
                          <div className="text-sm text-slate-500">
                            {c.translation}
                          </div>
                        </div>
                        <span className="shrink-0 px-2 py-0.5 rounded-full bg-slate-100 text-xs text-slate-600">
                          score {c.score.toFixed(1)}
                        </span>
                      </li>
                    ))}
                  </ul>
                </details>
              )}
            </>
          )}
        </>
      )}
    </div>
  );
}

function ParamSelect({
  label,
  value,
  options,
  onChange,
}: {
  label: string;
  value: string;
  options: { value: string; label: string }[];
  onChange: (v: string) => void;
}) {
  return (
    <label className="block">
      <span className="text-xs uppercase tracking-wide text-slate-500">
        {label}
      </span>
      <select
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className="mt-1 w-full appearance-none rounded-xl border border-slate-200 bg-white px-4 py-2.5 text-slate-900 focus:outline-none focus:ring-2 focus:ring-brand-400"
      >
        {options.map((o) => (
          <option key={o.value} value={o.value}>
            {o.label}
          </option>
        ))}
      </select>
    </label>
  );
}
