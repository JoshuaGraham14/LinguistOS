"use client";

import {
  BookOpen,
  Calendar,
  Check,
  ChevronDown,
  Download,
  Loader2,
  MessageSquare,
  Pencil,
  Plus,
  Search,
  Sparkles,
  SlidersHorizontal,
  Trash2,
  Upload,
} from "lucide-react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useEffect, useMemo, useRef, useState } from "react";
import { Modal } from "@/components/Modal";
import {
  enrichVocabSuggestion,
  suggestVocab,
  type VocabDraft,
  type VocabSuggestion,
  type VocabSuggestDirection,
} from "@/lib/api";
import { cn } from "@/lib/cn";
import { useVocab } from "@/lib/storage";
import {
  applyAutoSwappedSuggestion,
  fieldSwapHint,
  swappedFieldValues,
  type VocabFieldSwapHint,
} from "@/lib/vocabSuggestAutomation";
import type { VocabItem, VocabTag } from "@/lib/types";
import { ImportWordsModal } from "@/components/vocab/ImportWordsModal";
import { WordFormModal } from "@/components/vocab/WordFormModal";
import { buildVocabCsv, downloadVocabCsv } from "@/lib/vocab-csv";
import type { WordFormInput } from "@/lib/vocab-csv";


const TAG_OPTIONS: VocabTag[] = [
  "noun",
  "verb",
  "adjective",
  "adverb",
  "preposition",
  "other",
];

const TAG_COLORS: Record<VocabTag, string> = {
  noun: "bg-blue-100 text-blue-700",
  verb: "bg-emerald-100 text-emerald-700",
  adjective: "bg-amber-100 text-amber-700",
  adverb: "bg-pink-100 text-pink-700",
  preposition: "bg-indigo-100 text-indigo-700",
  other: "bg-slate-100 text-slate-700",
};

type SortOrder = "newest" | "oldest" | "alpha";
type LearnedFilter = "all" | "learned" | "unlearned";

const SORT_LABELS: Record<SortOrder, string> = {
  newest: "Newest First",
  oldest: "Oldest First",
  alpha: "Alphabetical",
};

const LEARNED_LABELS: Record<LearnedFilter, string> = {
  all: "All",
  learned: "Learned",
  unlearned: "Still learning",
};

function formatDate(ts: number) {
  return new Date(ts).toLocaleDateString("en-GB");
}

export default function WordsPage() {
  return (
    <Suspense fallback={null}>
      <WordsPageInner />
    </Suspense>
  );
}

function WordsPageInner() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const editParam = searchParams.get("edit");
  const {
    vocab,
    hydrated,
    addVocab,
    removeVocab,
    updateVocab,
    toggleLearned,
    clearVocab,
    activeWorkspace,
  } = useVocab();
  const [search, setSearch] = useState("");
  const [activeTags, setActiveTags] = useState<VocabTag[]>([]);
  const [learnedFilter, setLearnedFilter] = useState<LearnedFilter>("all");
  const [sort, setSort] = useState<SortOrder>("newest");
  const [sortOpen, setSortOpen] = useState(false);
  const [addOpen, setAddOpen] = useState(false);
  const [importOpen, setImportOpen] = useState(false);
  const [editing, setEditing] = useState<VocabItem | null>(null);
  const [confirmClear, setConfirmClear] = useState(false);

  // Open the edit modal from a deep link such as /words?edit=42
  // (used by Word Home's Edit action).
  useEffect(() => {
    if (!hydrated || !editParam) return;
    const id = Number(editParam);
    if (!Number.isFinite(id)) return;
    const target = vocab.find((v) => v.id === id);
    if (target) setEditing(target);
  }, [editParam, hydrated, vocab]);

  function closeEditing() {
    setEditing(null);
    if (editParam) router.replace("/words", { scroll: false });
  }

  function toggleActiveTag(tag: VocabTag) {
    setActiveTags((t) =>
      t.includes(tag) ? t.filter((x) => x !== tag) : [...t, tag],
    );
  }

  const learnedCount = useMemo(
    () => vocab.filter((v) => v.learned).length,
    [vocab],
  );

  const filtered = useMemo(() => {
    let list = vocab;
    if (search.trim()) {
      const q = search.trim().toLowerCase();
      list = list.filter(
        (v) =>
          v.word.toLowerCase().includes(q) ||
          v.translation.toLowerCase().includes(q),
      );
    }
    if (activeTags.length > 0) {
      list = list.filter((v) => v.tags.some((t) => activeTags.includes(t)));
    }
    if (learnedFilter === "learned") {
      list = list.filter((v) => v.learned);
    } else if (learnedFilter === "unlearned") {
      list = list.filter((v) => !v.learned);
    }
    const sorted = [...list];
    if (sort === "newest") sorted.sort((a, b) => b.createdAt - a.createdAt);
    else if (sort === "oldest") sorted.sort((a, b) => a.createdAt - b.createdAt);
    else sorted.sort((a, b) => a.word.localeCompare(b.word));
    return sorted;
  }, [vocab, search, activeTags, learnedFilter, sort]);

  function handleExport() {
    const stamp = new Date().toISOString().slice(0, 10);
    downloadVocabCsv(`linguistos-vocab-${stamp}.csv`, buildVocabCsv(vocab));
  }

  return (
    <div className="space-y-6">
      <header className="flex items-start justify-between gap-4 flex-wrap">
        <div>
          <h1 className="text-3xl font-bold text-slate-900">My Word Collection</h1>
          <p className="text-slate-500 mt-1">
            {hydrated ? (
              <>
                {vocab.length} word{vocab.length === 1 ? "" : "s"} ·{" "}
                <span className="text-emerald-600 font-medium">
                  {learnedCount} learned
                </span>
              </>
            ) : (
              "Loading…"
            )}
          </p>
        </div>
        <div className="flex gap-3 flex-wrap">
          <button
            type="button"
            onClick={handleExport}
            disabled={!hydrated || vocab.length === 0}
            className="inline-flex items-center gap-2 rounded-xl bg-white border border-slate-200 text-slate-700 font-medium px-4 py-3 shadow-soft hover:bg-slate-50 disabled:opacity-50 disabled:cursor-not-allowed transition"
          >
            <Download className="h-4 w-4" strokeWidth={2.5} />
            Export
          </button>
          <button
            type="button"
            onClick={() => setImportOpen(true)}
            className="inline-flex items-center gap-2 rounded-xl bg-gradient-to-r from-blue-500 to-blue-600 text-white font-medium px-5 py-3 shadow-soft hover:brightness-110 transition"
          >
            <Upload className="h-4 w-4" strokeWidth={2.5} />
            Import
          </button>
          <button
            type="button"
            onClick={() => setAddOpen(true)}
            className="inline-flex items-center gap-2 rounded-xl bg-btn-purple text-white font-medium px-5 py-3 shadow-soft hover:brightness-110 transition"
          >
            <Plus className="h-4 w-4" strokeWidth={2.5} />
            Add Word
          </button>
        </div>
      </header>

      <section className="glass-card rounded-2xl p-5 space-y-4">
        <div className="relative">
          <Search className="absolute left-4 top-1/2 -translate-y-1/2 h-5 w-5 text-slate-400" />
          <input
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search source word or translation..."
            className="w-full rounded-full bg-slate-50 border border-transparent pl-12 pr-4 py-3 text-slate-900 placeholder:text-slate-400 focus:outline-none focus:ring-2 focus:ring-brand-400 focus:bg-white"
          />
        </div>

        <div className="flex items-center gap-3 flex-wrap">
          <SlidersHorizontal className="h-4 w-4 text-slate-500" strokeWidth={2} />
          {TAG_OPTIONS.map((tag) => (
            <button
              type="button"
              key={tag}
              onClick={() => toggleActiveTag(tag)}
              className={cn(
                "px-4 py-1.5 rounded-full text-sm border transition capitalize",
                activeTags.includes(tag)
                  ? "bg-brand-100 border-brand-300 text-brand-700"
                  : "bg-white border-slate-200 text-slate-600 hover:bg-slate-50",
              )}
            >
              {tag}
            </button>
          ))}

          <div className="relative ml-auto">
            <button
              type="button"
              onClick={() => setSortOpen((o) => !o)}
              className="inline-flex items-center gap-2 rounded-xl bg-white border border-slate-200 px-4 py-2 text-sm text-slate-700 hover:bg-slate-50 transition"
            >
              <span className="text-slate-400">↕</span>
              {SORT_LABELS[sort]}
              <ChevronDown className="h-4 w-4 text-slate-400" />
            </button>
            {sortOpen && (
              <div
                className="glass-card-strong absolute right-0 top-full mt-1 w-44 rounded-xl py-1 z-10"
                onMouseLeave={() => setSortOpen(false)}
              >
                {(Object.keys(SORT_LABELS) as SortOrder[]).map((s) => (
                  <button
                    type="button"
                    key={s}
                    onClick={() => {
                      setSort(s);
                      setSortOpen(false);
                    }}
                    className="w-full flex items-center justify-between px-4 py-2 text-sm text-slate-700 hover:bg-slate-50"
                  >
                    {SORT_LABELS[s]}
                    {sort === s && <span className="text-emerald-500">✓</span>}
                  </button>
                ))}
              </div>
            )}
          </div>
        </div>

        <div className="flex items-center gap-2 flex-wrap">
          <span className="text-xs uppercase tracking-wide text-slate-500 mr-1">
            Status:
          </span>
          {(Object.keys(LEARNED_LABELS) as LearnedFilter[]).map((f) => (
            <button
              type="button"
              key={f}
              onClick={() => setLearnedFilter(f)}
              className={cn(
                "px-3 py-1 rounded-full text-xs border transition",
                learnedFilter === f
                  ? "bg-emerald-100 border-emerald-300 text-emerald-700"
                  : "bg-white border-slate-200 text-slate-600 hover:bg-slate-50",
              )}
            >
              {LEARNED_LABELS[f]}
            </button>
          ))}
          {hydrated && vocab.length > 0 && (
            <button
              type="button"
              onClick={() => setConfirmClear(true)}
              className="ml-auto inline-flex items-center gap-1 text-xs text-rose-600 hover:text-rose-700 hover:underline"
            >
              <Trash2 className="h-3.5 w-3.5" strokeWidth={2} />
              Clear all
            </button>
          )}
        </div>
      </section>

      {!hydrated ? (
        <p className="text-slate-400 text-center py-8">Loading…</p>
      ) : filtered.length === 0 ? (
        <p className="text-slate-500 text-center py-12">
          {vocab.length === 0
            ? "No words yet. Add your first one above."
            : "No matches for your filters."}
        </p>
      ) : (
        <section className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-5">
          {filtered.map((v) => (
            <WordCard
              key={v.id}
              item={v}
              onDelete={() => {
                void removeVocab(v.id);
              }}
              onEdit={() => setEditing(v)}
              onToggleLearned={() => {
                void toggleLearned(v.id);
              }}
            />
          ))}
        </section>
      )}

      <WordFormModal
        open={addOpen}
        onClose={() => setAddOpen(false)}
        title="Add a word"
        submitLabel="Add word"
        sourceLanguageLabel={activeWorkspace?.language.toUpperCase() ?? "Source"}
        workspaceId={activeWorkspace?.id ?? null}
        onSubmit={(values) => {
          void addVocab(values);
        }}
      />
      <WordFormModal
        open={editing !== null}
        onClose={closeEditing}
        title="Edit word"
        submitLabel="Save changes"
        initial={editing}
        sourceLanguageLabel={activeWorkspace?.language.toUpperCase() ?? "Source"}
        workspaceId={activeWorkspace?.id ?? null}
        onSubmit={(values) => {
          if (editing) void updateVocab(editing.id, values);
        }}
      />
      <ImportWordsModal
        open={importOpen}
        onClose={() => setImportOpen(false)}
        onImport={(rows) => {
          rows.forEach((r) => {
            void addVocab(r);
          });
        }}
      />
      <Modal
        open={confirmClear}
        onClose={() => setConfirmClear(false)}
        title="Clear all words?"
      >
        <div className="space-y-4">
          <p className="text-sm text-slate-600">
            This removes every word in your collection from this browser. There
            is no undo. Export first if you want a backup.
          </p>
          <div className="flex justify-end gap-2">
            <button
              type="button"
              onClick={() => setConfirmClear(false)}
              className="px-4 py-2 rounded-xl text-slate-600 hover:bg-slate-100 transition"
            >
              Cancel
            </button>
            <button
              type="button"
              onClick={() => {
                void clearVocab();
                setConfirmClear(false);
              }}
              className="px-5 py-2 rounded-xl bg-rose-500 text-white font-medium shadow-soft hover:bg-rose-600 transition"
            >
              Clear everything
            </button>
          </div>
        </div>
      </Modal>
    </div>
  );
}

function WordCard({
  item,
  onDelete,
  onEdit,
  onToggleLearned,
}: {
  item: VocabItem;
  onDelete: () => void;
  onEdit: () => void;
  onToggleLearned: () => void;
}) {
  return (
    <div
      className={cn(
        "glass-card rounded-2xl p-6 flex flex-col gap-4 group transition",
        item.learned && "ring-2 ring-emerald-300/60",
      )}
    >
      <div className="flex items-start justify-between gap-2">
        <button
          type="button"
          onClick={onToggleLearned}
          className={cn(
            "h-7 px-3 rounded-full text-xs font-medium transition inline-flex items-center gap-1",
            item.learned
              ? "bg-emerald-500 text-white hover:bg-emerald-600"
              : "bg-slate-100 text-slate-500 hover:bg-slate-200",
          )}
          aria-label={item.learned ? "Mark as still learning" : "Mark as learned"}
          title={item.learned ? "Mark as still learning" : "Mark as learned"}
        >
          <Check className="h-3 w-3" strokeWidth={3} />
          {item.learned ? "Learned" : "Mark learned"}
        </button>
        <div className="text-3xl font-bold text-slate-900 text-right break-words">
          {item.word}
        </div>
      </div>
      <div className="text-slate-600">{item.translation}</div>

      <div className="flex items-center gap-2">
        <Link
          href={`/learn/sentences?word=${encodeURIComponent(String(item.id))}`}
          className="h-9 px-3 rounded-full bg-fuchsia-500 text-white text-xs font-medium flex items-center gap-1 hover:bg-fuchsia-600 transition shadow-soft"
          aria-label="Practice with sentences"
          title="Practice this word with sentences"
        >
          <MessageSquare className="h-3.5 w-3.5" strokeWidth={2.5} />
          Sentences
        </Link>
        <Link
          href={`/learn/flashcards?word=${encodeURIComponent(String(item.id))}`}
          className="h-9 px-3 rounded-full bg-blue-500 text-white text-xs font-medium flex items-center gap-1 hover:bg-blue-600 transition shadow-soft"
          aria-label="Practice with flashcards"
          title="Practice this word with flashcards"
        >
          <BookOpen className="h-3.5 w-3.5" strokeWidth={2.5} />
          Flashcard
        </Link>
        <button
          type="button"
          onClick={onEdit}
          className="ml-auto h-9 w-9 rounded-full bg-amber-500 text-white flex items-center justify-center hover:bg-amber-600 transition shadow-soft"
          aria-label="Edit"
        >
          <Pencil className="h-4 w-4" strokeWidth={2.5} />
        </button>
        <button
          type="button"
          onClick={onDelete}
          className="p-2 rounded-lg text-slate-300 hover:text-rose-500 hover:bg-rose-50 transition opacity-0 group-hover:opacity-100"
          aria-label="Delete"
        >
          <Trash2 className="h-4 w-4" strokeWidth={2} />
        </button>
      </div>

      <div className="flex flex-wrap gap-1.5">
        {item.tags.length === 0 ? (
          <span
            className={cn(
              "text-xs px-3 py-1 rounded-full font-medium capitalize",
              TAG_COLORS.other,
            )}
          >
            other
          </span>
        ) : (
          item.tags.map((t, i) => (
            <span
              key={`${item.id}-${t}-${i}`}
              className={cn(
                "text-xs px-3 py-1 rounded-full font-medium capitalize",
                TAG_COLORS[t],
              )}
            >
              {t}
            </span>
          ))
        )}
      </div>

      <div className="flex items-center gap-1.5 text-xs text-slate-500 mt-auto">
        <Calendar className="h-3.5 w-3.5" strokeWidth={2} />
        {formatDate(item.createdAt)}
      </div>
    </div>
  );
}

