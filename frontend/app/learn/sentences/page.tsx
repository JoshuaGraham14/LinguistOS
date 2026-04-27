"use client";

import {
  ArrowLeft,
  ChevronLeft,
  ChevronRight,
  HelpCircle,
  Loader2,
  SkipForward,
} from "lucide-react";
import Link from "next/link";
import { useEffect, useMemo, useRef, useState } from "react";
import { SettingsPopover } from "@/components/SettingsPopover";
import { generateOrMock } from "@/lib/api";
import { cn } from "@/lib/cn";
import { usePracticeSettings, useVocab } from "@/lib/storage";
import type { PracticeSettings, SentenceCandidate } from "@/lib/types";

function normalize(s: string) {
  return s
    .trim()
    .toLowerCase()
    .replace(/[.,!?¿¡;:"']/g, "")
    .replace(/\s+/g, " ");
}

interface PromptPair {
  prompt: string;
  expected: string;
  promptLanguage: "en" | "es";
}

function pickPromptPair(
  candidate: SentenceCandidate | null,
  direction: PracticeSettings["direction"],
): PromptPair | null {
  if (!candidate || !candidate.translation) return null;
  if (direction === "en-to-es") {
    return {
      prompt: candidate.translation,
      expected: candidate.sentence,
      promptLanguage: "en",
    };
  }
  return {
    prompt: candidate.sentence,
    expected: candidate.translation,
    promptLanguage: "es",
  };
}

export default function SentencePracticePage() {
  const { vocab, hydrated } = useVocab();
  const { settings, setSettings, hydrated: settingsHydrated } =
    usePracticeSettings();

  const filteredVocab = useMemo(() => {
    if (settings.tagFilter.length === 0) return vocab;
    return vocab.filter((v) =>
      v.tags.some((t) => settings.tagFilter.includes(t)),
    );
  }, [vocab, settings.tagFilter]);

  const [wordIndex, setWordIndex] = useState(0);
  const [candidate, setCandidate] = useState<SentenceCandidate | null>(null);
  const [generating, setGenerating] = useState(false);
  const [isMock, setIsMock] = useState(false);

  const [answer, setAnswer] = useState("");
  const [feedback, setFeedback] = useState<"correct" | "incorrect" | null>(null);
  const [hintRevealed, setHintRevealed] = useState(false);

  const generationToken = useRef(0);

  useEffect(() => {
    if (wordIndex >= filteredVocab.length && filteredVocab.length > 0) {
      setWordIndex(0);
    }
  }, [filteredVocab.length, wordIndex]);

  const current = filteredVocab[wordIndex];

  const generateFor = useMemo(
    () => async (currentWord: typeof current) => {
      if (!currentWord) return;
      const myToken = ++generationToken.current;
      setGenerating(true);
      setCandidate(null);
      setAnswer("");
      setFeedback(null);
      setHintRevealed(false);
      try {
        const res = await generateOrMock({
          word: currentWord.word,
          translation: currentWord.translation,
          tense: settings.tense,
          person: settings.person,
          number: settings.number,
          sentence_length: settings.sentenceLength,
          direction: settings.direction,
          num_candidates: 1,
        });
        if (myToken !== generationToken.current) return;
        setCandidate(res.candidates[0] ?? null);
        setIsMock(Boolean(res.mock));
      } finally {
        if (myToken === generationToken.current) setGenerating(false);
      }
    },
    [
      settings.tense,
      settings.person,
      settings.number,
      settings.sentenceLength,
      settings.direction,
    ],
  );

  const currentId = current?.id;

  useEffect(() => {
    if (!hydrated || !settingsHydrated) return;
    if (!current) {
      setCandidate(null);
      return;
    }
    void generateFor(current);
    // generateFor already closes over the relevant settings; we re-run when
    // it changes (which happens when those settings change) or when the
    // selected word changes.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [hydrated, settingsHydrated, currentId, generateFor]);

  const pair = pickPromptPair(candidate, settings.direction);

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!pair) return;
    const ok = normalize(answer) === normalize(pair.expected);
    setFeedback(ok ? "correct" : "incorrect");
  }

  function handleSkip() {
    if (filteredVocab.length === 0) return;
    setWordIndex((i) => (i + 1) % filteredVocab.length);
  }

  function handleNotSure() {
    setHintRevealed(true);
  }

  function handlePrev() {
    if (filteredVocab.length === 0) return;
    setWordIndex(
      (i) => (i - 1 + filteredVocab.length) % filteredVocab.length,
    );
  }

  function handleNext() {
    if (filteredVocab.length === 0) return;
    setWordIndex((i) => (i + 1) % filteredVocab.length);
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
        <SettingsPopover settings={settings} onChange={setSettings} />
      </div>

      {!hydrated || !settingsHydrated ? (
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
      ) : filteredVocab.length === 0 ? (
        <div className="rounded-2xl bg-white/80 shadow-card p-12 text-center">
          <p className="text-slate-600">
            No words match the current tag filter. Adjust it from{" "}
            <span className="font-medium">Settings</span>.
          </p>
        </div>
      ) : (
        <>
          <section className="rounded-2xl bg-white/80 backdrop-blur shadow-card p-4 flex items-center justify-between gap-4">
            <button
              type="button"
              onClick={handlePrev}
              className="h-10 w-10 rounded-xl bg-slate-100 text-slate-700 flex items-center justify-center hover:bg-slate-200 transition"
              aria-label="Previous word"
            >
              <ChevronLeft className="h-5 w-5" strokeWidth={2.5} />
            </button>

            <div className="flex-1 text-center">
              <div className="text-xs uppercase tracking-wide text-slate-500">
                Practicing word {wordIndex + 1} of {filteredVocab.length}
              </div>
              <div className="text-2xl font-bold text-slate-900 mt-0.5">
                {current?.word}
              </div>
              <div className="text-sm text-slate-500">
                {current?.translation}
              </div>
            </div>

            <button
              type="button"
              onClick={handleNext}
              className="h-10 w-10 rounded-xl bg-slate-100 text-slate-700 flex items-center justify-center hover:bg-slate-200 transition"
              aria-label="Next word"
            >
              <ChevronRight className="h-5 w-5" strokeWidth={2.5} />
            </button>
          </section>

          <section className="rounded-3xl bg-gradient-to-br from-white via-white to-slate-50 shadow-card p-12 min-h-[280px] relative flex flex-col items-center justify-center">
            {isMock && (
              <div className="absolute top-4 right-4 px-3 py-1 rounded-full bg-amber-100 text-amber-700 text-xs font-medium">
                Demo mode
              </div>
            )}
            <button
              type="button"
              onClick={handleNotSure}
              className="absolute top-5 right-5 h-10 w-10 rounded-xl bg-slate-900 text-white flex items-center justify-center hover:bg-slate-800 transition"
              aria-label="Show hint"
              title="Reveal expected translation"
            >
              <HelpCircle className="h-5 w-5" strokeWidth={2} />
            </button>

            {generating ? (
              <div className="flex items-center gap-2 text-slate-500">
                <Loader2 className="h-5 w-5 animate-spin" />
                Generating sentence…
              </div>
            ) : pair ? (
              <>
                <div className="text-slate-500">Translate this sentence:</div>
                <div
                  className="mt-3 text-3xl md:text-4xl font-bold text-slate-900 text-center"
                  dir={pair.promptLanguage === "es" ? "ltr" : "ltr"}
                >
                  {pair.prompt}
                </div>
                {hintRevealed && (
                  <div className="mt-6 text-sm text-slate-500">
                    Expected:{" "}
                    <span className="font-medium text-slate-700">
                      {pair.expected}
                    </span>
                  </div>
                )}
              </>
            ) : (
              <div className="text-slate-500 text-sm text-center max-w-sm">
                Couldn&apos;t generate a sentence. Check that the backend is
                running and{" "}
                <code className="rounded bg-slate-100 px-1.5 py-0.5 text-xs text-slate-700">
                  OPENAI_API_KEY
                </code>{" "}
                is set, or use the seed words for demo mode.
              </div>
            )}
          </section>

          <div className="flex items-center justify-center gap-6 text-sm text-slate-600">
            <button
              type="button"
              onClick={handleNotSure}
              disabled={!pair}
              className="inline-flex items-center gap-1.5 hover:text-slate-900 disabled:opacity-50 disabled:cursor-not-allowed transition"
            >
              <HelpCircle className="h-4 w-4" strokeWidth={2} />
              Not sure
            </button>
            <button
              type="button"
              onClick={handleSkip}
              className="inline-flex items-center gap-1.5 hover:text-slate-900 transition"
            >
              <SkipForward className="h-4 w-4" strokeWidth={2} />
              Skip
            </button>
          </div>

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
              placeholder="Type your answer..."
              disabled={!pair || generating}
              className="w-full rounded-xl border border-slate-200 bg-white px-4 py-3 text-slate-900 placeholder:text-slate-400 focus:outline-none focus:ring-2 focus:ring-brand-400 disabled:bg-slate-50"
            />
            <div className="flex items-center justify-center">
              <button
                type="submit"
                disabled={!answer.trim() || !pair || generating}
                className={cn(
                  "rounded-xl px-8 py-2.5 font-medium text-white transition",
                  answer.trim() && pair && !generating
                    ? "bg-btn-purple hover:brightness-110 shadow-card"
                    : "bg-slate-300 cursor-not-allowed",
                )}
              >
                Submit
              </button>
            </div>
            {feedback && pair && (
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
                    <strong>{pair.expected}</strong>
                  </span>
                )}
              </div>
            )}
          </form>
        </>
      )}
    </div>
  );
}
