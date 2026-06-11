"use client";

import {
  Calendar,
  Check,
  ChevronLeft,
  ChevronRight,
  GraduationCap,
  RotateCcw,
  Shuffle,
  X,
} from "lucide-react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { Suspense, useCallback, useEffect, useMemo, useRef, useState } from "react";
import { cn } from "@/lib/cn";
import * as api from "@/lib/api";
import {
  applyLexiconQuery,
  isEmptyLexiconQuery,
  parseLexiconQuery,
} from "@/lib/lexicon-query";
import { useVocab } from "@/lib/storage";
import type { VocabItem } from "@/lib/types";

function shuffleArray<T>(arr: T[]): T[] {
  const copy = [...arr];
  for (let i = copy.length - 1; i > 0; i--) {
    const j = Math.floor(Math.random() * (i + 1));
    [copy[i], copy[j]] = [copy[j], copy[i]];
  }
  return copy;
}

function formatDate(ts: number) {
  return new Date(ts).toLocaleDateString("en-GB");
}

function formatTime(seconds: number) {
  const m = Math.floor(seconds / 60);
  const s = seconds % 60;
  return `${m}:${s.toString().padStart(2, "0")}`;
}

function FlashcardsInner() {
  const { vocab, hydrated, toggleLearned, recordOutcome } = useVocab();
  const searchParams = useSearchParams();
  const wordParam = searchParams.get("word");
  const filterParam = searchParams.get("filter");
  const viewParam = searchParams.get("view");
  const [viewFilterReady, setViewFilterReady] = useState(!viewParam);
  const [viewScopedIds, setViewScopedIds] = useState<Set<number> | null>(null);

  useEffect(() => {
    if (!viewParam) {
      setViewScopedIds(null);
      setViewFilterReady(true);
      return;
    }
    const viewId = Number(viewParam);
    if (!Number.isFinite(viewId)) {
      setViewScopedIds(null);
      setViewFilterReady(true);
      return;
    }
    let cancelled = false;
    setViewFilterReady(false);
    void api
      .getSavedView(viewId)
      .then((view) => {
        if (cancelled) return;
        const filtered = applyLexiconQuery(vocab, view.config.query);
        setViewScopedIds(new Set(filtered.map((v) => v.id)));
        setViewFilterReady(true);
      })
      .catch(() => {
        if (!cancelled) {
          setViewScopedIds(null);
          setViewFilterReady(true);
        }
      });
    return () => {
      cancelled = true;
    };
  }, [viewParam, vocab]);

  const [shuffle, setShuffle] = useState(true);
  const [direction, setDirection] = useState<"en-to-es" | "es-to-en">("en-to-es");
  const [order, setOrder] = useState<VocabItem[]>([]);
  const [index, setIndex] = useState(0);
  const [revealed, setRevealed] = useState(false);
  const [seconds, setSeconds] = useState(0);
  const [stats, setStats] = useState({ knew: 0, didnt: 0 });
  const [finished, setFinished] = useState(false);

  const scopedVocab = useMemo(() => {
    // Single-word focus (existing behaviour) takes precedence over the
    // lexicon filter so deep links to one word continue to work.
    if (wordParam) {
      const wordId = Number(wordParam);
      const match = Number.isFinite(wordId)
        ? vocab.find((v) => v.id === wordId)
        : undefined;
      return match ? [match] : vocab;
    }
    if (viewParam && viewScopedIds) {
      return vocab.filter((v) => viewScopedIds.has(v.id));
    }
    if (filterParam) {
      const query = parseLexiconQuery(decodeURIComponent(filterParam));
      if (!isEmptyLexiconQuery(query)) {
        return applyLexiconQuery(vocab, query);
      }
    }
    return vocab;
  }, [vocab, wordParam, filterParam, viewParam, viewScopedIds]);

  // Build deck whenever vocab/shuffle/scope changes; resets the session.
  useEffect(() => {
    if (!hydrated || !viewFilterReady) return;
    setOrder(shuffle ? shuffleArray(scopedVocab) : scopedVocab);
    setIndex(0);
    setRevealed(false);
    setStats({ knew: 0, didnt: 0 });
    setSeconds(0);
    setFinished(false);
  }, [scopedVocab, hydrated, shuffle, viewFilterReady]);

  // Timer ticks while studying; pauses on finish/empty deck.
  useEffect(() => {
    if (!hydrated || finished || order.length === 0) return;
    const id = setInterval(() => setSeconds((s) => s + 1), 1000);
    return () => clearInterval(id);
  }, [hydrated, finished, order.length]);

  const current = order[index];
  const total = order.length;

  const front = useMemo(() => {
    if (!current) return "";
    return direction === "en-to-es" ? current.translation : current.word;
  }, [current, direction]);

  const back = useMemo(() => {
    if (!current) return "";
    return direction === "en-to-es" ? current.word : current.translation;
  }, [current, direction]);

  const handlePrev = useCallback(() => {
    if (finished) return;
    setRevealed(false);
    setIndex((i) => Math.max(0, i - 1));
  }, [finished]);

  const handleNext = useCallback(() => {
    if (finished) return;
    setRevealed(false);
    setIndex((i) => Math.min(total - 1, i + 1));
  }, [finished, total]);

  const handleKnew = useCallback(() => {
    if (!current || finished) return;
    if (!current.learned) toggleLearned(current.id);
    void recordOutcome(current.id, "correct", "flashcards");
    setStats((s) => ({ ...s, knew: s.knew + 1 }));
    if (index >= total - 1) {
      setFinished(true);
      setRevealed(false);
    } else {
      setRevealed(false);
      setIndex((i) => i + 1);
    }
  }, [current, finished, index, total, toggleLearned, recordOutcome]);

  const handleDidntKnow = useCallback(() => {
    if (!current || finished) return;
    void recordOutcome(current.id, "incorrect", "flashcards");
    setStats((s) => ({ ...s, didnt: s.didnt + 1 }));
    if (index >= total - 1) {
      setFinished(true);
      setRevealed(false);
    } else {
      setRevealed(false);
      setIndex((i) => i + 1);
    }
  }, [current, finished, index, total, recordOutcome]);

  const handleRestart = useCallback(() => {
    setIndex(0);
    setRevealed(false);
    setStats({ knew: 0, didnt: 0 });
    setSeconds(0);
    setFinished(false);
  }, []);

  const handleReshuffle = useCallback(() => {
    setOrder((o) => shuffleArray(o));
    handleRestart();
  }, [handleRestart]);

  const toggleReveal = useCallback(() => {
    if (!current || finished) return;
    setRevealed((r) => !r);
  }, [current, finished]);

  // Keyboard shortcuts: space=flip, ←/→=prev/next, J=didn't know, K=knew it, R=restart
  useEffect(() => {
    function handleKey(e: KeyboardEvent) {
      const target = e.target as HTMLElement | null;
      if (target && (target.tagName === "INPUT" || target.tagName === "TEXTAREA"))
        return;
      if (finished) {
        if (e.key.toLowerCase() === "r") {
          e.preventDefault();
          handleRestart();
        }
        return;
      }
      if (!current) return;
      if (e.key === " " || e.code === "Space") {
        e.preventDefault();
        toggleReveal();
      } else if (e.key === "ArrowLeft") {
        e.preventDefault();
        handlePrev();
      } else if (e.key === "ArrowRight") {
        e.preventDefault();
        handleNext();
      } else if (revealed && e.key.toLowerCase() === "j") {
        e.preventDefault();
        handleDidntKnow();
      } else if (revealed && e.key.toLowerCase() === "k") {
        e.preventDefault();
        handleKnew();
      }
    }
    document.addEventListener("keydown", handleKey);
    return () => document.removeEventListener("keydown", handleKey);
  }, [
    current,
    finished,
    revealed,
    toggleReveal,
    handlePrev,
    handleNext,
    handleKnew,
    handleDidntKnow,
    handleRestart,
  ]);

  return (
    <div className="space-y-6">
      <div className="flex items-start justify-between gap-4">
        <header>
          {viewParam && !wordParam && (
            <Link
              href={`/vocab?view=${viewParam}`}
              className="inline-flex items-center gap-1 text-sm text-fuchsia-700 hover:text-fuchsia-800 font-medium mb-2"
            >
              <ChevronLeft className="h-4 w-4" />
              Back to vocabulary
            </Link>
          )}
          <h1 className="text-3xl font-bold text-slate-900">Flashcards</h1>
          <p className="text-slate-500 mt-1">
            Flip, score, and review your workspace deck.
          </p>
        </header>
        <div className="text-right">
          <div className="text-sm text-slate-500">
            {total > 0 && !finished
              ? `${index + 1} of ${total}`
              : `${total} of ${total}`}
          </div>
          <div className="text-fuchsia-600 font-bold">
            Time: {formatTime(seconds)}
          </div>
        </div>
      </div>

      {wordParam && current && (
        <div className="rounded-xl bg-blue-50 border border-blue-100 px-4 py-2 text-sm text-blue-700">
          Practicing a single word from your collection.{" "}
          <Link href="/learn/flashcards" className="underline">
            Switch to full deck
          </Link>
          .
        </div>
      )}

      {!wordParam && viewParam && (
        <div className="rounded-xl bg-fuchsia-50 border border-fuchsia-100 px-4 py-2 text-sm text-fuchsia-700 flex flex-wrap items-center gap-x-2 gap-y-1">
          <GraduationCap className="h-4 w-4 shrink-0" />
          <span>
            Practicing saved vocabulary view ({total} words).
          </span>
          <Link href={`/vocab?view=${viewParam}`} className="underline font-medium">
            Back to view
          </Link>
          <span aria-hidden>·</span>
          <Link href="/learn/flashcards" className="underline">
            Use full deck
          </Link>
        </div>
      )}

      {!wordParam && !viewParam && filterParam && (
        <div className="rounded-xl bg-fuchsia-50 border border-fuchsia-100 px-4 py-2 text-sm text-fuchsia-700">
          Practicing filtered deck ({total} words).{" "}
          <Link href="/vocab" className="underline">
            Open vocabulary
          </Link>{" "}
          ·{" "}
          <Link href="/learn/flashcards" className="underline">
            Use full deck
          </Link>
        </div>
      )}

      <div className="glass-card rounded-2xl px-6 py-4 flex items-center justify-center gap-10">
        <ToggleSwitch label="Shuffle" checked={shuffle} onChange={setShuffle} />
        <ToggleSwitch
          label="English → Spanish"
          checked={direction === "en-to-es"}
          onChange={(v) => setDirection(v ? "en-to-es" : "es-to-en")}
        />
      </div>

      {total > 0 && (
        <div className="h-1 bg-slate-200 rounded-full overflow-hidden">
          <div
            className="h-full bg-gradient-to-r from-fuchsia-500 to-purple-600 transition-all duration-300"
            style={{
              width: `${
                finished ? 100 : ((index + (revealed ? 1 : 0)) / total) * 100
              }%`,
            }}
          />
        </div>
      )}

      {finished ? (
        <SessionSummary
          knew={stats.knew}
          didnt={stats.didnt}
          seconds={seconds}
          onRestart={handleRestart}
          onReshuffle={handleReshuffle}
        />
      ) : (
        <>
          <div className="flex items-center gap-4">
            <button
              type="button"
              onClick={handlePrev}
              disabled={index === 0}
              className="h-10 w-10 rounded-xl bg-slate-700 text-white flex items-center justify-center hover:bg-slate-800 disabled:opacity-40 disabled:cursor-not-allowed transition"
              aria-label="Previous"
            >
              <ChevronLeft className="h-5 w-5" strokeWidth={2.5} />
            </button>

            <button
              type="button"
              onClick={toggleReveal}
              disabled={!current}
              className="flex-1 glass-card-strong glass-gloss rounded-3xl p-12 min-h-[360px] relative flex flex-col items-center justify-center group disabled:opacity-50"
            >
              {current ? (
                <>
                  <div className="text-4xl md:text-5xl font-bold text-slate-900 text-center">
                    {revealed ? back : front}
                  </div>
                  <div className="text-xs text-slate-400 mt-6">
                    {revealed ? "Tap to flip back · space" : "Tap to reveal · space"}
                  </div>
                </>
              ) : (
                <div className="text-slate-500 text-center">
                  {hydrated
                    ? "No words yet. Add some on the Words page."
                    : "Loading…"}
                </div>
              )}

              {current && (
                <div className="absolute bottom-5 left-5 flex items-center gap-1.5 text-xs text-slate-500">
                  <Calendar className="h-3.5 w-3.5" strokeWidth={2} />
                  {formatDate(current.createdAt)}
                </div>
              )}
            </button>

            <button
              type="button"
              onClick={handleNext}
              disabled={index >= total - 1}
              className="h-10 w-10 rounded-xl bg-slate-700 text-white flex items-center justify-center hover:bg-slate-800 disabled:opacity-40 disabled:cursor-not-allowed transition"
              aria-label="Next"
            >
              <ChevronRight className="h-5 w-5" strokeWidth={2.5} />
            </button>
          </div>

          {revealed && current && (
            <div className="flex items-center justify-center gap-3">
              <button
                type="button"
                onClick={handleDidntKnow}
                className="inline-flex items-center gap-2 px-6 py-3 rounded-xl bg-rose-500 text-white font-medium shadow-soft hover:bg-rose-600 transition"
              >
                <X className="h-4 w-4" strokeWidth={2.5} />
                Didn&apos;t Know
                <kbd className="ml-1 px-1.5 py-0.5 rounded bg-rose-700/40 text-[10px]">J</kbd>
              </button>
              <button
                type="button"
                onClick={handleKnew}
                className="inline-flex items-center gap-2 px-6 py-3 rounded-xl bg-emerald-500 text-white font-medium shadow-soft hover:bg-emerald-600 transition"
              >
                <Check className="h-4 w-4" strokeWidth={2.5} />
                I Knew It
                <kbd className="ml-1 px-1.5 py-0.5 rounded bg-emerald-700/40 text-[10px]">K</kbd>
              </button>
            </div>
          )}

          <div className="text-center text-xs text-slate-400">
            Shortcuts: space = flip · ← → = navigate · J / K = didn&apos;t / knew
          </div>
        </>
      )}
    </div>
  );
}

function SessionSummary({
  knew,
  didnt,
  seconds,
  onRestart,
  onReshuffle,
}: {
  knew: number;
  didnt: number;
  seconds: number;
  onRestart: () => void;
  onReshuffle: () => void;
}) {
  const total = knew + didnt;
  const accuracy = total > 0 ? Math.round((knew / total) * 100) : 0;

  return (
    <div className="rounded-3xl bg-white/90 backdrop-blur shadow-card p-10 text-center space-y-6">
      <div>
        <div className="text-4xl">🎉</div>
        <h2 className="text-2xl font-bold text-slate-900 mt-2">Session complete</h2>
        <p className="text-slate-500 mt-1">
          {total} card{total === 1 ? "" : "s"} reviewed in {formatTime(seconds)}
        </p>
      </div>

      <div className="grid grid-cols-3 gap-3 max-w-md mx-auto">
        <div className="rounded-2xl bg-emerald-50 p-4">
          <div className="text-2xl font-bold text-emerald-600">{knew}</div>
          <div className="text-xs text-emerald-700 mt-0.5">Knew it</div>
        </div>
        <div className="rounded-2xl bg-rose-50 p-4">
          <div className="text-2xl font-bold text-rose-600">{didnt}</div>
          <div className="text-xs text-rose-700 mt-0.5">Didn&apos;t know</div>
        </div>
        <div className="rounded-2xl bg-slate-50 p-4">
          <div className="text-2xl font-bold text-slate-700">{accuracy}%</div>
          <div className="text-xs text-slate-500 mt-0.5">Accuracy</div>
        </div>
      </div>

      <div className="flex items-center justify-center gap-3">
        <button
          type="button"
          onClick={onRestart}
          className="inline-flex items-center gap-2 px-5 py-2.5 rounded-xl bg-slate-100 text-slate-700 font-medium hover:bg-slate-200 transition"
        >
          <RotateCcw className="h-4 w-4" strokeWidth={2.5} />
          Restart
          <kbd className="ml-1 px-1.5 py-0.5 rounded bg-slate-300 text-[10px] text-slate-700">R</kbd>
        </button>
        <button
          type="button"
          onClick={onReshuffle}
          className="inline-flex items-center gap-2 px-5 py-2.5 rounded-xl bg-btn-purple text-white font-medium shadow-soft hover:brightness-110 transition"
        >
          <Shuffle className="h-4 w-4" strokeWidth={2.5} />
          Reshuffle
        </button>
      </div>
    </div>
  );
}

function ToggleSwitch({
  label,
  checked,
  onChange,
}: {
  label: string;
  checked: boolean;
  onChange: (v: boolean) => void;
}) {
  return (
    <div className="flex items-center gap-3">
      <span className="text-slate-700 text-sm font-medium">{label}</span>
      <button
        type="button"
        onClick={() => onChange(!checked)}
        className={cn(
          "relative h-6 w-11 rounded-full transition shrink-0",
          checked ? "bg-slate-900" : "bg-slate-300",
        )}
        aria-label={`Toggle ${label}`}
      >
        <span
          className={cn(
            "absolute top-0.5 h-5 w-5 rounded-full bg-white shadow transition",
            checked ? "left-5" : "left-0.5",
          )}
        />
      </button>
    </div>
  );
}

export default function FlashcardsPage() {
  return (
    <Suspense fallback={<div className="text-slate-400 text-center py-12">Loading…</div>}>
      <FlashcardsInner />
    </Suspense>
  );
}
