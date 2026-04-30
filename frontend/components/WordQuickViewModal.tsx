"use client";

import {
  BookOpen,
  Calendar,
  MessageSquare,
  Sparkles,
  X,
} from "lucide-react";
import Link from "next/link";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { useEffect, useMemo, useState } from "react";
import * as api from "@/lib/api";
import { cn } from "@/lib/cn";
import { formatWordDisplay, useProfile, useVocab } from "@/lib/storage";
import type { SentenceRecord, VocabItem } from "@/lib/types";
import { TokenizedText } from "./TokenizedText";

function formatDate(ts: number | null) {
  if (!ts) return "-";
  return new Date(ts).toLocaleString();
}

function StatTile({
  label,
  value,
  hint,
}: {
  label: string;
  value: string;
  hint?: string;
}) {
  return (
    <div className="rounded-xl bg-slate-50/80 border border-slate-200 p-3">
      <div className="text-[11px] uppercase tracking-wide text-slate-500">{label}</div>
      <div className="text-xl font-bold text-slate-900 mt-0.5">{value}</div>
      {hint && <div className="text-xs text-slate-500 mt-0.5">{hint}</div>}
    </div>
  );
}

export function WordQuickViewModal() {
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const quickIdParam = searchParams.get("word_quick");
  const quickId = Number(quickIdParam);
  const isOpen = Number.isFinite(quickId) && quickId > 0;

  const { vocab, activeWorkspace } = useVocab();
  const { profile } = useProfile();

  const item = useMemo<VocabItem | undefined>(() => {
    if (!isOpen) return undefined;
    return vocab.find((v) => v.id === quickId);
  }, [vocab, quickId, isOpen]);

  const [sentences, setSentences] = useState<SentenceRecord[]>([]);
  const [sentencesLoading, setSentencesLoading] = useState(false);

  useEffect(() => {
    if (!isOpen || !activeWorkspace || !item) {
      setSentences([]);
      return;
    }
    let cancelled = false;
    (async () => {
      setSentencesLoading(true);
      try {
        const list = await api.listSentences({
          workspaceId: activeWorkspace.id,
          vocabId: item.id,
          limit: 20,
        });
        if (!cancelled) setSentences(list);
      } catch {
        if (!cancelled) setSentences([]);
      } finally {
        if (!cancelled) setSentencesLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [isOpen, activeWorkspace, item]);

  useEffect(() => {
    if (!isOpen) return;
    function onKey(event: KeyboardEvent) {
      if (event.key === "Escape") close();
    }
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  });

  function close() {
    const next = new URLSearchParams(searchParams.toString());
    next.delete("word_quick");
    const q = next.toString();
    router.replace(q ? `${pathname}?${q}` : pathname, { scroll: false });
  }

  if (!isOpen) return null;

  return (
    <div
      className="fixed inset-0 z-[90] bg-slate-900/30 backdrop-blur-sm flex items-center justify-center p-4"
      onClick={close}
    >
      <section
        role="dialog"
        aria-modal="true"
        aria-label="Word quick view"
        onClick={(e) => e.stopPropagation()}
        className="w-[min(1100px,94vw)] h-[min(88vh,820px)] rounded-2xl bg-white shadow-2xl border border-slate-200 overflow-hidden"
      >
        {!item ? (
          <div className="h-full flex items-center justify-center text-slate-500">
            Word not found in this workspace.
          </div>
        ) : (
          <WordQuickViewBody
            item={item}
            sentences={sentences}
            sentencesLoading={sentencesLoading}
            onClose={close}
            displayMode={profile.wordDisplayMode}
          />
        )}
      </section>
    </div>
  );
}

function WordQuickViewBody({
  item,
  sentences,
  sentencesLoading,
  onClose,
  displayMode,
}: {
  item: VocabItem;
  sentences: SentenceRecord[];
  sentencesLoading: boolean;
  onClose: () => void;
  displayMode: "lemma_first" | "as_encountered";
}) {
  const display = formatWordDisplay(item, displayMode);
  const mastery = item.mastery;
  const formsSeen = (item.surfaceForms ?? []).filter((f) => f && f !== item.lemma);

  return (
    <div className="h-full overflow-auto p-6 md:p-8 space-y-6">
      <header className="flex items-start justify-between gap-4">
        <div>
          <div className="text-xs uppercase tracking-wide text-slate-500">Word quick view</div>
          <h2 className="text-3xl font-bold text-slate-900 mt-1">{display.primary}</h2>
          {display.secondary && <p className="text-slate-500">{display.secondary}</p>}
          <p className="text-lg text-slate-700 mt-2">{item.glossPrimary || item.translation}</p>
        </div>
        <button
          type="button"
          onClick={onClose}
          className="h-10 w-10 rounded-xl bg-slate-100 text-slate-600 hover:bg-slate-200 transition flex items-center justify-center"
          aria-label="Close quick view"
        >
          <X className="h-5 w-5" strokeWidth={2.2} />
        </button>
      </header>

      <div className="flex gap-2 flex-wrap">
        <Link
          href={`/words/${item.id}`}
          className="inline-flex items-center gap-2 rounded-xl bg-slate-900 text-white px-4 py-2 text-sm font-medium hover:bg-slate-800 transition"
        >
          Open full Word Home
        </Link>
        <Link
          href={`/learn/flashcards?word=${item.id}`}
          className="inline-flex items-center gap-2 rounded-xl bg-blue-500 text-white px-4 py-2 text-sm font-medium hover:bg-blue-600 transition"
        >
          <BookOpen className="h-4 w-4" strokeWidth={2.3} /> Flashcards
        </Link>
        <Link
          href={`/learn/sentences?word=${item.id}`}
          className="inline-flex items-center gap-2 rounded-xl bg-fuchsia-500 text-white px-4 py-2 text-sm font-medium hover:bg-fuchsia-600 transition"
        >
          <MessageSquare className="h-4 w-4" strokeWidth={2.3} /> Sentences
        </Link>
      </div>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <StatTile label="Box" value={String(mastery?.box ?? 0)} hint="Leitner level" />
        <StatTile
          label="Strength"
          value={`${Math.round((mastery?.strength ?? 0) * 100)}%`}
          hint={`${mastery?.successes ?? 0} ✓ / ${mastery?.failures ?? 0} ✗`}
        />
        <StatTile label="Streak" value={String(mastery?.streak ?? 0)} hint="Consecutive correct" />
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

      <section className="rounded-2xl bg-white border border-slate-200 p-5 space-y-3">
        <h3 className="text-base font-semibold text-slate-900 flex items-center gap-2">
          <Sparkles className="h-4 w-4 text-fuchsia-500" /> Forms seen
        </h3>
        {formsSeen.length === 0 ? (
          <p className="text-sm text-slate-500">No additional forms seen yet.</p>
        ) : (
          <div className="flex flex-wrap gap-2">
            {formsSeen.map((form) => (
              <span key={form} className="px-3 py-1 rounded-full bg-slate-100 text-slate-700 text-sm">
                {form}
              </span>
            ))}
          </div>
        )}
      </section>

      <section className="rounded-2xl bg-white border border-slate-200 p-5 space-y-3">
        <h3 className="text-base font-semibold text-slate-900 flex items-center gap-2">
          <Calendar className="h-4 w-4 text-fuchsia-500" /> Sentences seen
        </h3>
        {sentencesLoading ? (
          <p className="text-sm text-slate-400">Loading sentences...</p>
        ) : sentences.length === 0 ? (
          <p className="text-sm text-slate-500">No saved sentences for this word yet.</p>
        ) : (
          <ul className="divide-y divide-slate-100">
            {sentences.map((s) => (
              <li key={s.id} className="py-3">
                <p className="text-slate-900">
                  <TokenizedText
                    text={s.text}
                    language={s.language}
                    sourceContext={{ type: "word_quick_view_sentence", id: s.id }}
                  />
                </p>
                {s.translation && <p className="text-sm text-slate-500 mt-0.5">{s.translation}</p>}
                <p className="text-xs text-slate-400 mt-1 capitalize">{s.source}</p>
              </li>
            ))}
          </ul>
        )}
      </section>

      <div className={cn("text-xs text-slate-400", item.notes && "pb-2")}>
        {item.notes ? `Notes: ${item.notes}` : ""}
      </div>
    </div>
  );
}
