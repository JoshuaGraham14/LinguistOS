"use client";

import {
  ArrowLeft,
  Calendar,
  Check,
  ChevronLeft,
  ChevronRight,
  X,
} from "lucide-react";
import Link from "next/link";
import { useEffect, useMemo, useRef, useState } from "react";
import { cn } from "@/lib/cn";
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

export default function FlashcardsPage() {
  const { vocab, hydrated, toggleLearned } = useVocab();
  const [shuffle, setShuffle] = useState(true);
  const [direction, setDirection] = useState<"en-to-es" | "es-to-en">("en-to-es");
  const [order, setOrder] = useState<VocabItem[]>([]);
  const [index, setIndex] = useState(0);
  const [revealed, setRevealed] = useState(false);
  const [seconds, setSeconds] = useState(0);
  const [stats, setStats] = useState({ knew: 0, didnt: 0 });
  const startedRef = useRef(false);

  useEffect(() => {
    if (!hydrated) return;
    setOrder(shuffle ? shuffleArray(vocab) : vocab);
    setIndex(0);
    setRevealed(false);
  }, [vocab, hydrated, shuffle]);

  useEffect(() => {
    if (!hydrated || vocab.length === 0) return;
    if (!startedRef.current) startedRef.current = true;
    const id = setInterval(() => setSeconds((s) => s + 1), 1000);
    return () => clearInterval(id);
  }, [hydrated, vocab.length]);

  const current = order[index];

  const front = useMemo(() => {
    if (!current) return "";
    return direction === "en-to-es" ? current.translation : current.word;
  }, [current, direction]);

  const back = useMemo(() => {
    if (!current) return "";
    return direction === "en-to-es" ? current.word : current.translation;
  }, [current, direction]);

  function handleNext() {
    setRevealed(false);
    setIndex((i) => Math.min(order.length - 1, i + 1));
  }

  function handlePrev() {
    setRevealed(false);
    setIndex((i) => Math.max(0, i - 1));
  }

  function handleKnew() {
    if (!current) return;
    if (!current.learned) toggleLearned(current.id);
    setStats((s) => ({ ...s, knew: s.knew + 1 }));
    handleNext();
  }

  function handleDidntKnow() {
    setStats((s) => ({ ...s, didnt: s.didnt + 1 }));
    handleNext();
  }

  const atEnd = index >= order.length - 1 && revealed;
  const total = order.length;

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
        <div className="text-right">
          <div className="text-sm text-slate-500">
            {total > 0 ? `${index + 1} of ${total}` : "0 of 0"}
          </div>
          <div className="text-fuchsia-600 font-bold">
            Time: {formatTime(seconds)}
          </div>
        </div>
      </div>

      <div className="rounded-2xl bg-white/80 backdrop-blur shadow-card px-6 py-4 flex items-center justify-center gap-10">
        <ToggleSwitch
          label="Shuffle"
          checked={shuffle}
          onChange={setShuffle}
        />
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
            style={{ width: `${((index + 1) / total) * 100}%` }}
          />
        </div>
      )}

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
          onClick={() => setRevealed((r) => !r)}
          disabled={!current}
          className="flex-1 rounded-3xl bg-white/90 shadow-card p-12 min-h-[360px] relative flex flex-col items-center justify-center group disabled:opacity-50"
        >
          {current ? (
            <>
              <div className="text-4xl md:text-5xl font-bold text-slate-900 text-center">
                {revealed ? back : front}
              </div>
              <div className="text-xs text-slate-400 mt-6">
                {revealed ? "Tap to flip back" : "Tap to reveal"}
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
            Didn't Know
          </button>
          <button
            type="button"
            onClick={handleKnew}
            className="inline-flex items-center gap-2 px-6 py-3 rounded-xl bg-emerald-500 text-white font-medium shadow-soft hover:bg-emerald-600 transition"
          >
            <Check className="h-4 w-4" strokeWidth={2.5} />
            I Knew It
          </button>
        </div>
      )}

      {atEnd && (
        <div className="rounded-2xl bg-white/80 backdrop-blur shadow-card p-6 text-center">
          <div className="text-lg font-semibold text-slate-900">
            Session complete
          </div>
          <div className="text-sm text-slate-500 mt-1">
            Knew: <span className="text-emerald-600 font-medium">{stats.knew}</span>{" "}
            · Didn't know:{" "}
            <span className="text-rose-600 font-medium">{stats.didnt}</span>
          </div>
        </div>
      )}
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
