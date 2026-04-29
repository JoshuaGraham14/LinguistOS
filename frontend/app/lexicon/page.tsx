"use client";

import {
  ArrowDownUp,
  BookOpen,
  CalendarClock,
  Filter,
  MessageSquare,
  Search as SearchIcon,
  X,
} from "lucide-react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useEffect, useMemo, useState } from "react";
import { cn } from "@/lib/cn";
import {
  EMPTY_QUERY,
  applyLexiconQuery,
  isEmptyLexiconQuery,
  parseLexiconQuery,
  serializeLexiconQuery,
  type DueFilter,
  type LearnedFilter,
  type LexiconQuery,
} from "@/lib/lexicon-query";
import { formatWordDisplay, useProfile, useVocab } from "@/lib/storage";
import type { VocabItem, VocabTag } from "@/lib/types";

const TAG_OPTIONS: VocabTag[] = [
  "noun",
  "verb",
  "adjective",
  "adverb",
  "preposition",
  "other",
];

const POS_OPTIONS = ["noun", "verb", "adjective", "adverb", "preposition"];
const CEFR_OPTIONS = ["A1", "A2", "B1", "B2", "C1", "C2"];

const LEARNED_LABELS: Record<LearnedFilter, string> = {
  any: "All",
  learned: "Learned",
  not_learned: "Still learning",
};

const DUE_LABELS: Record<DueFilter, string> = {
  any: "Any due",
  due_now: "Due now",
  due_week: "Due this week",
  not_due: "Not due",
};

function formatDate(ts: number | null) {
  if (!ts) return "—";
  return new Date(ts).toLocaleDateString("en-GB");
}

function LexiconInner() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const { vocab, hydrated } = useVocab();
  const { profile } = useProfile();

  const [query, setQuery] = useState<LexiconQuery>(() =>
    parseLexiconQuery(searchParams.toString()),
  );

  // Whenever the query changes, push it to the URL so the view is shareable
  // and so flashcards can pick it up via ?filter=.
  useEffect(() => {
    const serialized = serializeLexiconQuery(query);
    const target = serialized ? `/lexicon?${serialized}` : "/lexicon";
    router.replace(target, { scroll: false });
  }, [query, router]);

  const filtered = useMemo(
    () => applyLexiconQuery(vocab, query),
    [vocab, query],
  );

  const filterEncoded = serializeLexiconQuery(query);

  function toggleInList<T extends string>(
    list: T[],
    value: T,
    setNext: (next: T[]) => void,
  ) {
    if (list.includes(value)) setNext(list.filter((v) => v !== value));
    else setNext([...list, value]);
  }

  return (
    <div className="space-y-6">
      <header className="flex items-start justify-between gap-4 flex-wrap">
        <div>
          <h1 className="text-3xl font-bold text-slate-900">Lexicon</h1>
          <p className="text-slate-500 mt-1">
            {hydrated
              ? `${filtered.length} of ${vocab.length} words match`
              : "Loading…"}
          </p>
        </div>
        <div className="flex gap-2 flex-wrap">
          <Link
            href={
              filterEncoded
                ? `/learn/flashcards?filter=${encodeURIComponent(filterEncoded)}`
                : "/learn/flashcards"
            }
            className="inline-flex items-center gap-2 rounded-xl bg-blue-500 text-white font-medium px-4 py-2.5 shadow-soft hover:bg-blue-600 transition"
          >
            <BookOpen className="h-4 w-4" strokeWidth={2.5} />
            Flashcards from this view
          </Link>
          {!isEmptyLexiconQuery(query) && (
            <button
              type="button"
              onClick={() => setQuery({ ...EMPTY_QUERY })}
              className="inline-flex items-center gap-2 rounded-xl bg-white border border-slate-200 text-slate-700 font-medium px-4 py-2.5 hover:bg-slate-50 transition"
            >
              <X className="h-4 w-4" strokeWidth={2.5} />
              Reset filters
            </button>
          )}
        </div>
      </header>

      <section className="rounded-2xl bg-white/80 backdrop-blur shadow-card p-5 space-y-4">
        <div className="relative">
          <SearchIcon className="absolute left-4 top-1/2 -translate-y-1/2 h-5 w-5 text-slate-400" />
          <input
            value={query.search}
            onChange={(e) => setQuery({ ...query, search: e.target.value })}
            placeholder="Search lemma, surface form, or translation…"
            className="w-full rounded-full bg-slate-50 border border-transparent pl-12 pr-4 py-3 text-slate-900 placeholder:text-slate-400 focus:outline-none focus:ring-2 focus:ring-brand-400 focus:bg-white"
          />
        </div>

        <div className="flex items-center gap-2 flex-wrap">
          <span className="inline-flex items-center gap-1 text-xs uppercase tracking-wide text-slate-500 mr-1">
            <Filter className="h-3.5 w-3.5" /> Tags
          </span>
          {TAG_OPTIONS.map((tag) => (
            <button
              type="button"
              key={tag}
              onClick={() =>
                toggleInList(query.tags, tag, (next) =>
                  setQuery({ ...query, tags: next }),
                )
              }
              className={cn(
                "px-3 py-1 rounded-full text-xs border transition capitalize",
                query.tags.includes(tag)
                  ? "bg-brand-100 border-brand-300 text-brand-700"
                  : "bg-white border-slate-200 text-slate-600 hover:bg-slate-50",
              )}
            >
              {tag}
            </button>
          ))}
        </div>

        <div className="flex items-center gap-2 flex-wrap">
          <span className="text-xs uppercase tracking-wide text-slate-500 mr-1">
            POS
          </span>
          {POS_OPTIONS.map((pos) => (
            <button
              type="button"
              key={pos}
              onClick={() =>
                toggleInList(query.pos, pos, (next) =>
                  setQuery({ ...query, pos: next }),
                )
              }
              className={cn(
                "px-3 py-1 rounded-full text-xs border transition capitalize",
                query.pos.includes(pos)
                  ? "bg-emerald-100 border-emerald-300 text-emerald-700"
                  : "bg-white border-slate-200 text-slate-600 hover:bg-slate-50",
              )}
            >
              {pos}
            </button>
          ))}
        </div>

        <div className="flex items-center gap-2 flex-wrap">
          <span className="text-xs uppercase tracking-wide text-slate-500 mr-1">
            CEFR
          </span>
          {CEFR_OPTIONS.map((c) => (
            <button
              type="button"
              key={c}
              onClick={() =>
                toggleInList(query.cefr, c, (next) =>
                  setQuery({ ...query, cefr: next }),
                )
              }
              className={cn(
                "px-3 py-1 rounded-full text-xs border transition",
                query.cefr.includes(c)
                  ? "bg-fuchsia-100 border-fuchsia-300 text-fuchsia-700"
                  : "bg-white border-slate-200 text-slate-600 hover:bg-slate-50",
              )}
            >
              {c}
            </button>
          ))}
        </div>

        <div className="flex items-center gap-2 flex-wrap">
          <span className="text-xs uppercase tracking-wide text-slate-500 mr-1">
            Status
          </span>
          {(Object.keys(LEARNED_LABELS) as LearnedFilter[]).map((f) => (
            <button
              type="button"
              key={f}
              onClick={() => setQuery({ ...query, learned: f })}
              className={cn(
                "px-3 py-1 rounded-full text-xs border transition",
                query.learned === f
                  ? "bg-amber-100 border-amber-300 text-amber-700"
                  : "bg-white border-slate-200 text-slate-600 hover:bg-slate-50",
              )}
            >
              {LEARNED_LABELS[f]}
            </button>
          ))}

          <span className="ml-3 inline-flex items-center gap-1 text-xs uppercase tracking-wide text-slate-500 mr-1">
            <CalendarClock className="h-3.5 w-3.5" /> Due
          </span>
          {(Object.keys(DUE_LABELS) as DueFilter[]).map((f) => (
            <button
              type="button"
              key={f}
              onClick={() => setQuery({ ...query, due: f })}
              className={cn(
                "px-3 py-1 rounded-full text-xs border transition",
                query.due === f
                  ? "bg-rose-100 border-rose-300 text-rose-700"
                  : "bg-white border-slate-200 text-slate-600 hover:bg-slate-50",
              )}
            >
              {DUE_LABELS[f]}
            </button>
          ))}
        </div>
      </section>

      <section className="rounded-2xl bg-white/80 backdrop-blur shadow-card overflow-hidden">
        <div className="overflow-x-auto">
          <table className="min-w-full text-sm">
            <thead className="bg-slate-50 text-slate-500 uppercase text-xs tracking-wide">
              <tr>
                <th className="px-4 py-2 text-left">Word</th>
                <th className="px-4 py-2 text-left">Lemma</th>
                <th className="px-4 py-2 text-left">Translation</th>
                <th className="px-4 py-2 text-left">POS</th>
                <th className="px-4 py-2 text-left">CEFR</th>
                <th className="px-4 py-2 text-left">Tags</th>
                <th className="px-4 py-2 text-left">Box</th>
                <th className="px-4 py-2 text-left">Next due</th>
                <th className="px-4 py-2"></th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {!hydrated ? (
                <tr>
                  <td colSpan={9} className="px-4 py-12 text-center text-slate-400">
                    Loading…
                  </td>
                </tr>
              ) : filtered.length === 0 ? (
                <tr>
                  <td colSpan={9} className="px-4 py-12 text-center text-slate-500">
                    No words match this view.
                  </td>
                </tr>
              ) : (
                filtered.map((v) => (
                  <LexiconRow key={v.id} item={v} mode={profile.wordDisplayMode} />
                ))
              )}
            </tbody>
          </table>
        </div>
      </section>

      <p className="text-xs text-slate-400 inline-flex items-center gap-1.5">
        <ArrowDownUp className="h-3 w-3" />
        Sorting and saved views are coming next.
      </p>
    </div>
  );
}

function LexiconRow({
  item,
  mode,
}: {
  item: VocabItem;
  mode: "lemma_first" | "as_encountered";
}) {
  const display = formatWordDisplay(item, mode);
  return (
    <tr className="hover:bg-slate-50/50">
      <td className="px-4 py-2 font-medium text-slate-900">
        <Link href={`/words/${item.id}`} className="hover:text-brand-700">
          {display.primary}
        </Link>
        {display.secondary && (
          <div className="text-xs text-slate-400">{display.secondary}</div>
        )}
      </td>
      <td className="px-4 py-2 text-slate-700">{item.lemma ?? item.word}</td>
      <td className="px-4 py-2 text-slate-700">
        {item.glossPrimary || item.translation}
      </td>
      <td className="px-4 py-2 text-slate-600 capitalize">{item.pos ?? "—"}</td>
      <td className="px-4 py-2 text-slate-600">{item.cefr ?? "—"}</td>
      <td className="px-4 py-2">
        <div className="flex flex-wrap gap-1">
          {item.tags.length === 0 ? (
            <span className="text-xs text-slate-400">—</span>
          ) : (
            item.tags.map((t) => (
              <span
                key={t}
                className="text-xs px-2 py-0.5 rounded-full bg-slate-100 text-slate-600 capitalize"
              >
                {t}
              </span>
            ))
          )}
        </div>
      </td>
      <td className="px-4 py-2 text-slate-700">{item.mastery?.box ?? 0}</td>
      <td className="px-4 py-2 text-slate-600">
        {formatDate(item.mastery?.nextDue ?? null)}
      </td>
      <td className="px-4 py-2 text-right">
        <Link
          href={`/learn/sentences?word=${item.id}`}
          className="inline-flex items-center gap-1 text-xs text-fuchsia-600 hover:text-fuchsia-700"
        >
          <MessageSquare className="h-3.5 w-3.5" />
          Practice
        </Link>
      </td>
    </tr>
  );
}

export default function LexiconPage() {
  return (
    <Suspense fallback={<div className="text-slate-400 text-center py-12">Loading…</div>}>
      <LexiconInner />
    </Suspense>
  );
}
