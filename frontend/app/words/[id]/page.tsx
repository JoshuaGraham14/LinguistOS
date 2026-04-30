"use client";

import {
  ArrowLeft,
  BookOpen,
  Calendar,
  Check,
  MessageSquare,
  Pencil,
  Sparkles,
  Trash2,
  X,
} from "lucide-react";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useEffect, useMemo, useState } from "react";
import * as api from "@/lib/api";
import { cn } from "@/lib/cn";
import { formatWordDisplay, useProfile, useVocab } from "@/lib/storage";
import type { SentenceRecord, VocabItem } from "@/lib/types";

function formatDate(ts: number | null) {
  if (!ts) return "—";
  return new Date(ts).toLocaleString();
}

function StatTile({
  label,
  value,
  hint,
  className,
}: {
  label: string;
  value: string;
  hint?: string;
  className?: string;
}) {
  return (
    <div className={cn("rounded-xl bg-white/80 backdrop-blur shadow-card p-4", className)}>
      <div className="text-xs uppercase tracking-wide text-slate-500">{label}</div>
      <div className="text-2xl font-bold text-slate-900 mt-1">{value}</div>
      {hint && <div className="text-xs text-slate-500 mt-1">{hint}</div>}
    </div>
  );
}

export default function WordHomePage() {
  const router = useRouter();
  const params = useParams<{ id: string }>();
  const wordId = Number(params?.id);

  const { vocab, hydrated, removeVocab, activeWorkspace } = useVocab();
  const { profile } = useProfile();

  const item = useMemo<VocabItem | undefined>(
    () => vocab.find((v) => v.id === wordId),
    [vocab, wordId],
  );

  const [sentences, setSentences] = useState<SentenceRecord[]>([]);
  const [sentencesLoading, setSentencesLoading] = useState(false);

  useEffect(() => {
    let cancelled = false;
    async function fetchSentences() {
      if (!activeWorkspace || !Number.isFinite(wordId)) return;
      setSentencesLoading(true);
      try {
        const list = await api.listSentences({
          workspaceId: activeWorkspace.id,
          vocabId: wordId,
          limit: 25,
        });
        if (!cancelled) setSentences(list);
      } catch {
        if (!cancelled) setSentences([]);
      } finally {
        if (!cancelled) setSentencesLoading(false);
      }
    }
    void fetchSentences();
    return () => {
      cancelled = true;
    };
  }, [activeWorkspace, wordId]);

  if (!hydrated) {
    return (
      <div className="text-slate-400 text-center py-16">Loading word…</div>
    );
  }

  if (!item) {
    return (
      <div className="space-y-6">
        <Link
          href="/lexicon"
          className="inline-flex items-center gap-2 rounded-2xl bg-white shadow-card px-5 py-3 text-slate-700 font-medium hover:bg-slate-50 transition"
        >
          <ArrowLeft className="h-5 w-5" strokeWidth={1.75} />
          Back to lexicon
        </Link>
        <div className="rounded-2xl bg-white/80 shadow-card p-12 text-center text-slate-500">
          That word isn’t in your lexicon.
        </div>
      </div>
    );
  }

  const display = formatWordDisplay(item, profile.wordDisplayMode);
  const mastery = item.mastery;
  const formsSeen = (item.surfaceForms ?? []).filter(
    (f) => f && f !== item.lemma,
  );

  async function handleDelete() {
    if (!item) return;
    if (!window.confirm(`Delete "${item.surfaceForm ?? item.word}"?`)) return;
    await removeVocab(item.id);
    router.push("/lexicon");
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between flex-wrap gap-3">
        <Link
          href="/lexicon"
          className="inline-flex items-center gap-2 rounded-2xl bg-white shadow-card px-5 py-3 text-slate-700 font-medium hover:bg-slate-50 transition"
        >
          <ArrowLeft className="h-5 w-5" strokeWidth={1.75} />
          Back to lexicon
        </Link>
        <div className="flex gap-2">
          <Link
            href={`/learn/flashcards?word=${item.id}`}
            className="inline-flex items-center gap-2 rounded-xl bg-blue-500 text-white font-medium px-4 py-2.5 shadow-soft hover:bg-blue-600 transition"
          >
            <BookOpen className="h-4 w-4" strokeWidth={2.5} />
            Flashcard
          </Link>
          <Link
            href={`/learn/sentences?word=${item.id}`}
            className="inline-flex items-center gap-2 rounded-xl bg-fuchsia-500 text-white font-medium px-4 py-2.5 shadow-soft hover:bg-fuchsia-600 transition"
          >
            <MessageSquare className="h-4 w-4" strokeWidth={2.5} />
            Sentences
          </Link>
          <Link
            href={`/words?edit=${item.id}`}
            className="inline-flex items-center gap-2 rounded-xl bg-white border border-slate-200 text-slate-700 font-medium px-4 py-2.5 hover:bg-slate-50 transition"
          >
            <Pencil className="h-4 w-4" strokeWidth={2} />
            Edit
          </Link>
          <button
            type="button"
            onClick={handleDelete}
            className="inline-flex items-center gap-2 rounded-xl bg-white border border-rose-200 text-rose-600 font-medium px-4 py-2.5 hover:bg-rose-50 transition"
          >
            <Trash2 className="h-4 w-4" strokeWidth={2} />
            Delete
          </button>
        </div>
      </div>

      <header className="rounded-2xl bg-gradient-to-br from-white via-white to-brand-50/40 shadow-card p-8">
        <div className="flex items-baseline gap-4 flex-wrap">
          <h1 className="text-4xl font-bold text-slate-900">{display.primary}</h1>
          {display.secondary && (
            <span className="text-lg text-slate-500">({display.secondary})</span>
          )}
          {item.cefr && (
            <span className="text-xs px-2 py-0.5 rounded-full bg-fuchsia-100 text-fuchsia-700">
              {item.cefr}
            </span>
          )}
          {item.pos && (
            <span className="text-xs px-2 py-0.5 rounded-full bg-emerald-100 text-emerald-700 capitalize">
              {item.pos}
            </span>
          )}
          {item.learned ? (
            <span className="inline-flex items-center gap-1 text-xs px-2 py-0.5 rounded-full bg-emerald-100 text-emerald-700">
              <Check className="h-3 w-3" /> Learned
            </span>
          ) : (
            <span className="inline-flex items-center gap-1 text-xs px-2 py-0.5 rounded-full bg-slate-100 text-slate-600">
              <X className="h-3 w-3" /> Still learning
            </span>
          )}
        </div>
        <p className="text-xl text-slate-700 mt-2">
          {item.glossPrimary || item.translation}
        </p>
        {item.glosses && item.glosses.length > 1 && (
          <p className="text-sm text-slate-500 mt-1">
            Other meanings: {item.glosses.slice(1).join(", ")}
          </p>
        )}
        {item.notes && (
          <p className="text-sm text-slate-600 mt-3 italic">{item.notes}</p>
        )}
        {item.tags.length > 0 && (
          <div className="flex flex-wrap gap-2 mt-4">
            {item.tags.map((tag) => (
              <span
                key={tag}
                className="text-xs px-2 py-0.5 rounded-full bg-slate-100 text-slate-600 capitalize"
              >
                {tag}
              </span>
            ))}
          </div>
        )}
      </header>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <StatTile
          label="Box"
          value={String(mastery?.box ?? 0)}
          hint="Leitner schedule level"
        />
        <StatTile
          label="Strength"
          value={`${Math.round(((mastery?.strength ?? 0) * 100))}%`}
          hint={`${mastery?.successes ?? 0} ✓ / ${mastery?.failures ?? 0} ✗`}
        />
        <StatTile
          label="Streak"
          value={String(mastery?.streak ?? 0)}
          hint="Consecutive correct"
        />
        <StatTile
          label="Next due"
          value={formatDate(mastery?.nextDue ?? null)}
          hint={
            mastery?.lastReviewedAt
              ? `Last reviewed ${formatDate(mastery.lastReviewedAt)}`
              : "Not reviewed yet"
          }
        />
      </div>

      <section className="rounded-2xl bg-white/80 backdrop-blur shadow-card p-6 space-y-4">
        <h2 className="text-lg font-semibold text-slate-900 flex items-center gap-2">
          <Sparkles className="h-4 w-4 text-fuchsia-500" />
          Forms seen
        </h2>
        {formsSeen.length === 0 ? (
          <p className="text-sm text-slate-500">
            Only {item.lemma ?? item.surfaceForm ?? item.word} has been seen so
            far. Other forms will appear here as you encounter them.
          </p>
        ) : (
          <div className="flex flex-wrap gap-2">
            {formsSeen.map((form) => (
              <span
                key={form}
                className="inline-flex items-center gap-1 rounded-full bg-slate-100 text-slate-700 px-3 py-1 text-sm"
              >
                {form}
              </span>
            ))}
          </div>
        )}
      </section>

      <section className="rounded-2xl bg-white/80 backdrop-blur shadow-card p-6 space-y-3">
        <div className="flex items-center justify-between">
          <h2 className="text-lg font-semibold text-slate-900 flex items-center gap-2">
            <Calendar className="h-4 w-4 text-fuchsia-500" />
            Sentences seen
          </h2>
          <Link
            href={`/learn/sentences?word=${item.id}`}
            className="text-sm text-fuchsia-600 hover:text-fuchsia-700"
          >
            Practice with this word →
          </Link>
        </div>
        {sentencesLoading ? (
          <p className="text-sm text-slate-400">Loading sentences…</p>
        ) : sentences.length === 0 ? (
          <p className="text-sm text-slate-500">
            No saved sentences for this word yet. Generated sentences from
            practice will appear here as they are saved.
          </p>
        ) : (
          <ul className="divide-y divide-slate-100">
            {sentences.map((s) => (
              <li key={s.id} className="py-3">
                <p className="text-slate-900">{s.text}</p>
                {s.translation && (
                  <p className="text-sm text-slate-500 mt-0.5">{s.translation}</p>
                )}
                <p className="text-xs text-slate-400 mt-1 capitalize">
                  {s.source}
                </p>
              </li>
            ))}
          </ul>
        )}
      </section>
    </div>
  );
}
