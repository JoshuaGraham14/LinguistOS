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

interface WordFormValues {
  word: string;
  translation: string;
  tags: VocabTag[];
  surfaceForm?: string;
  glossPrimary?: string;
  glosses?: string[];
  lemma?: string;
  pos?: string | null;
  cefr?: string | null;
  frequencyRank?: number | null;
  gender?: string | null;
  conjugationClass?: string | null;
  morphFeatures?: Record<string, unknown> | null;
  ipa?: string | null;
  notes?: string | null;
}

function escapeCsv(value: string) {
  if (/[",\n]/.test(value)) return `"${value.replace(/"/g, '""')}"`;
  return value;
}

function buildCsv(items: VocabItem[]) {
  const lines = ["word,translation,tags,learned"];
  for (const item of items) {
    lines.push(
      [
        escapeCsv(item.word),
        escapeCsv(item.translation),
        escapeCsv(item.tags.join(";")),
        item.learned ? "true" : "false",
      ].join(","),
    );
  }
  return lines.join("\n") + "\n";
}

function downloadCsv(filename: string, contents: string) {
  const blob = new Blob([contents], { type: "text/csv;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
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
    downloadCsv(`linguistos-vocab-${stamp}.csv`, buildCsv(vocab));
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

function WordFormModal({
  open,
  onClose,
  onSubmit,
  title,
  submitLabel,
  sourceLanguageLabel,
  workspaceId,
  initial,
}: {
  open: boolean;
  onClose: () => void;
  onSubmit: (input: WordFormValues) => void;
  title: string;
  submitLabel: string;
  sourceLanguageLabel: string;
  workspaceId: number | null;
  initial?: VocabItem | null;
}) {
  const [word, setWord] = useState(initial?.word ?? "");
  const [translation, setTranslation] = useState(initial?.translation ?? "");
  const [tags, setTags] = useState<VocabTag[]>(initial?.tags ?? []);
  const [activeSide, setActiveSide] = useState<"target" | "english">("target");
  const [suggestions, setSuggestions] = useState<VocabSuggestion[]>([]);
  const [suggesting, setSuggesting] = useState(false);
  const [enriching, setEnriching] = useState(false);
  const [autoError, setAutoError] = useState<string | null>(null);
  const [draft, setDraft] = useState<VocabDraft | null>(null);
  const [selectionLocked, setSelectionLocked] = useState(false);
  const [swapHint, setSwapHint] = useState<VocabFieldSwapHint | null>(null);
  const suggestSeq = useRef(0);
  const enrichSeq = useRef(0);
  const isEditing = Boolean(initial);
  const targetLanguageCode = sourceLanguageLabel.toLowerCase();

  useEffect(() => {
    if (!open) return;
    setWord(initial?.word ?? "");
    setTranslation(initial?.translation ?? "");
    setTags(initial?.tags ?? []);
    setActiveSide("target");
    setSuggestions([]);
    setSuggesting(false);
    setEnriching(false);
    setAutoError(null);
    setDraft(null);
    setSelectionLocked(false);
    setSwapHint(null);
  }, [open, initial?.id, initial?.word, initial?.translation, initial?.tags]);

  const direction: VocabSuggestDirection =
    activeSide === "english" ? "en-to-target" : "target-to-en";
  const activeText = activeSide === "english" ? translation : word;

  useEffect(() => {
    if (!open || isEditing || selectionLocked || !workspaceId) {
      setSuggestions([]);
      setSuggesting(false);
      return;
    }
    const query = activeText.trim();
    if (query.length < 2) {
      setSuggestions([]);
      setSuggesting(false);
      return;
    }

    const seq = ++suggestSeq.current;
    setSuggesting(true);
    setAutoError(null);
    const timer = window.setTimeout(() => {
      void suggestVocab({
        workspaceId,
        inputText: query,
        direction,
      })
        .then(async (res) => {
          if (seq !== suggestSeq.current) return;
          if (res.fieldSwap && res.candidates.length > 0) {
            setSwapHint(fieldSwapHint(direction, targetLanguageCode));
            setEnriching(true);
            const applied = await applyAutoSwappedSuggestion({
              workspaceId,
              query,
              result: res,
              enrichSeq,
            });
            if (seq !== suggestSeq.current) return;
            const values = swappedFieldValues(
              query,
              applied.candidate,
              applied.direction,
              applied.draft,
            );
            setWord(values.target);
            setTranslation(values.english);
            setActiveSide(applied.direction === "en-to-target" ? "english" : "target");
            setDraft(applied.draft);
            if (applied.draft?.tags.length) {
              setTags(applied.draft.tags);
            } else {
              setTags([applied.candidate.pos]);
            }
            setSelectionLocked(true);
            setSuggestions(res.candidates.length > 1 ? res.candidates.slice(1) : []);
            setSuggesting(false);
            setEnriching(false);
            if (applied.error) setAutoError(applied.error);
            return;
          }
          setSwapHint(null);
          setSuggestions(res.candidates);
          setSuggesting(false);
        })
        .catch(() => {
          if (seq !== suggestSeq.current) return;
          setSuggestions([]);
          setSuggesting(false);
          setSwapHint(null);
          setAutoError("Could not load translation options");
        });
    }, 350);

    return () => window.clearTimeout(timer);
  }, [activeText, direction, isEditing, open, selectionLocked, workspaceId]);

  function resetAutomation(side: "target" | "english") {
    setActiveSide(side);
    setSelectionLocked(false);
    setDraft(null);
    setSwapHint(null);
    setAutoError(null);
  }

  function toggleTag(tag: VocabTag) {
    setTags((t) =>
      t.includes(tag) ? t.filter((x) => x !== tag) : [...t, tag],
    );
  }

  async function chooseSuggestion(candidate: VocabSuggestion) {
    if (!workspaceId || enriching) return;
    const inputText = activeText.trim();
    if (!inputText) return;

    const seq = ++enrichSeq.current;
    setSelectionLocked(true);
    setSuggestions([]);
    setSuggesting(false);
    setEnriching(true);
    setAutoError(null);

    if (direction === "en-to-target") {
      setWord(candidate.text);
      setTranslation(inputText);
    } else {
      setWord(inputText);
      setTranslation(candidate.text);
    }
    setTags([candidate.pos]);

    try {
      const res = await enrichVocabSuggestion({
        workspaceId,
        inputText,
        selectedText: candidate.text,
        direction,
        pos: candidate.pos,
      });
      if (seq !== enrichSeq.current) return;
      setDraft(res.draft);
      setWord(res.draft.surfaceForm);
      setTranslation(res.draft.glossPrimary);
      setTags(res.draft.tags.length ? res.draft.tags : [res.draft.pos]);
    } catch {
      if (seq !== enrichSeq.current) return;
      setDraft({
        surfaceForm: direction === "en-to-target" ? candidate.text : inputText,
        lemma: direction === "en-to-target" ? candidate.text : inputText,
        glossPrimary: direction === "en-to-target" ? inputText : candidate.text,
        glosses: [direction === "en-to-target" ? inputText : candidate.text],
        pos: candidate.pos,
        tags: [candidate.pos],
        cefr: null,
        frequencyRank: null,
        gender: null,
        conjugationClass: null,
        morphFeatures: null,
        ipa: null,
        notes: null,
      });
      setAutoError("Metadata could not be prepared; you can still save this word");
    } finally {
      if (seq === enrichSeq.current) setEnriching(false);
    }
  }

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    const surface = word.trim();
    const gloss = translation.trim();
    if (!surface || !gloss || enriching) return;
    onSubmit({
      word: surface,
      translation: gloss,
      tags,
      surfaceForm: draft?.surfaceForm ?? surface,
      glossPrimary: draft?.glossPrimary ?? gloss,
      glosses: draft?.glosses ?? [gloss],
      lemma: draft?.lemma ?? surface,
      pos: draft?.pos ?? tags[0] ?? null,
      cefr: draft?.cefr ?? null,
      frequencyRank: draft?.frequencyRank ?? null,
      gender: draft?.gender ?? null,
      conjugationClass: draft?.conjugationClass ?? null,
      morphFeatures: draft?.morphFeatures ?? null,
      ipa: draft?.ipa ?? null,
      notes: draft?.notes ?? null,
    });
    onClose();
  }

  const activeInputClass =
    "ring-2 ring-brand-300 border-brand-200 bg-white";

  return (
    <Modal open={open} onClose={onClose} title={title}>
      <form onSubmit={handleSubmit} className="space-y-4">
        <label className="block">
          <span className="text-sm font-medium text-slate-700">{sourceLanguageLabel}</span>
          <input
            value={word}
            onFocus={() => setActiveSide("target")}
            onChange={(e) => {
              resetAutomation("target");
              setWord(e.target.value);
            }}
            placeholder="e.g. correr"
            autoFocus
            className={cn(
              "mt-1 w-full rounded-xl border border-slate-200 px-4 py-2.5 focus:outline-none focus:ring-2 focus:ring-brand-400",
              !isEditing && activeSide === "target" && activeInputClass,
            )}
          />
        </label>
        <label className="block">
          <span className="text-sm font-medium text-slate-700">English</span>
          <input
            value={translation}
            onFocus={() => setActiveSide("english")}
            onChange={(e) => {
              resetAutomation("english");
              setTranslation(e.target.value);
            }}
            placeholder="e.g. to run"
            className={cn(
              "mt-1 w-full rounded-xl border border-slate-200 px-4 py-2.5 focus:outline-none focus:ring-2 focus:ring-brand-400",
              !isEditing && activeSide === "english" && activeInputClass,
            )}
          />
        </label>

        {!isEditing && (
          <div className="rounded-xl border border-slate-200 bg-white/70 p-3 min-h-[76px]">
            <div className="flex items-center justify-between gap-3">
              <span className="inline-flex items-center gap-1.5 text-xs font-medium text-slate-600">
                <Sparkles className="h-3.5 w-3.5 text-brand-500" strokeWidth={2.5} />
                {activeSide === "english"
                  ? `English to ${sourceLanguageLabel}`
                  : `${sourceLanguageLabel} to English`}
              </span>
              {(suggesting || enriching) && (
                <span className="inline-flex items-center gap-1.5 text-xs text-slate-500">
                  <Loader2 className="h-3.5 w-3.5 animate-spin" />
                  {enriching ? "Preparing word" : "Finding options"}
                </span>
              )}
            </div>

            {suggestions.length > 0 ? (
              <div className="mt-3 flex flex-col gap-2">
                {suggestions.map((candidate) => (
                  <button
                    type="button"
                    key={`${candidate.text}-${candidate.pos}`}
                    onClick={() => {
                      void chooseSuggestion(candidate);
                    }}
                    className="rounded-xl border border-brand-200 bg-brand-50 px-3 py-2 text-left text-sm text-brand-700 hover:bg-brand-100 transition"
                  >
                    <span className="font-semibold">{candidate.text}</span>
                    <span className="ml-1.5 text-xs uppercase tracking-wide text-brand-500">
                      {candidate.pos}
                    </span>
                    {candidate.context ? (
                      <span className="mt-0.5 block text-xs font-normal text-slate-500">
                        {candidate.context}
                      </span>
                    ) : null}
                  </button>
                ))}
              </div>
            ) : (
              <p className="mt-3 text-xs text-slate-500">
                {swapHint ? (
                  <span className="text-brand-700">{swapHint.message}</span>
                ) : activeText.trim().length < 2 ? (
                  "Type either side to look up direct translations."
                ) : selectionLocked ? (
                  "Translation selected. Metadata is ready to save."
                ) : suggesting || enriching ? (
                  "Looking for direct translations..."
                ) : (
                  "No direct options yet. You can still enter both sides manually."
                )}
              </p>
            )}
            {autoError && <p className="mt-2 text-xs text-rose-600">{autoError}</p>}
          </div>
        )}

        <div>
          <span className="text-sm font-medium text-slate-700">Tags</span>
          <div className="mt-2 flex flex-wrap gap-2">
            {TAG_OPTIONS.map((tag) => (
              <button
                type="button"
                key={tag}
                onClick={() => toggleTag(tag)}
                className={cn(
                  "px-3 py-1.5 rounded-full text-sm border transition capitalize",
                  tags.includes(tag)
                    ? "bg-brand-100 border-brand-300 text-brand-700"
                    : "bg-white border-slate-200 text-slate-600 hover:bg-slate-50",
                )}
              >
                {tag}
              </button>
            ))}
          </div>
        </div>
        <div className="flex justify-end gap-2 pt-2">
          <button
            type="button"
            onClick={onClose}
            className="px-4 py-2 rounded-xl text-slate-600 hover:bg-slate-100 transition"
          >
            Cancel
          </button>
          <button
            type="submit"
            disabled={!word.trim() || !translation.trim() || enriching}
            className="px-5 py-2 rounded-xl bg-btn-purple text-white font-medium shadow-soft hover:brightness-110 disabled:opacity-50 disabled:cursor-not-allowed transition"
          >
            {enriching ? "Preparing…" : submitLabel}
          </button>
        </div>
      </form>
    </Modal>
  );
}

const VALID_TAGS: VocabTag[] = [
  "noun",
  "verb",
  "adjective",
  "adverb",
  "preposition",
  "other",
];

function parseImportText(text: string): WordFormValues[] {
  const rows: WordFormValues[] = [];
  for (const rawLine of text.split(/\r?\n/)) {
    const line = rawLine.trim();
    if (!line || line.startsWith("#")) continue;
    if (line.toLowerCase().startsWith("word,translation")) continue;
    const parts = line.split(",").map((p) => p.trim());
    if (parts.length < 2) continue;
    const [word, translation, rawTags] = parts;
    if (!word || !translation) continue;
    const tags: VocabTag[] = (rawTags ?? "")
      .split(";")
      .map((t) => t.trim().toLowerCase())
      .filter((t): t is VocabTag => (VALID_TAGS as string[]).includes(t));
    rows.push({ word, translation, tags });
  }
  return rows;
}

function ImportWordsModal({
  open,
  onClose,
  onImport,
}: {
  open: boolean;
  onClose: () => void;
  onImport: (rows: WordFormValues[]) => void;
}) {
  const [text, setText] = useState("");
  const [error, setError] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const parsed = useMemo(() => parseImportText(text), [text]);

  function handleFile(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file) return;
    const reader = new FileReader();
    reader.onload = () => {
      const result = reader.result;
      if (typeof result === "string") setText(result);
      setError(null);
    };
    reader.onerror = () => setError("Could not read file");
    reader.readAsText(file);
  }

  function handleImport() {
    if (parsed.length === 0) {
      setError("No valid rows found");
      return;
    }
    onImport(parsed);
    setText("");
    setError(null);
    if (fileInputRef.current) fileInputRef.current.value = "";
    onClose();
  }

  function handleClose() {
    setText("");
    setError(null);
    if (fileInputRef.current) fileInputRef.current.value = "";
    onClose();
  }

  return (
    <Modal open={open} onClose={handleClose} title="Import words">
      <div className="space-y-4">
        <p className="text-sm text-slate-600">
          One word per line, comma-separated:{" "}
          <code className="rounded bg-slate-100 px-1.5 py-0.5 text-xs text-slate-700">
            spanish,english,tag1;tag2
          </code>
          . Blank lines and lines starting with{" "}
          <code className="rounded bg-slate-100 px-1.5 py-0.5 text-xs text-slate-700">
            #
          </code>{" "}
          are ignored.
        </p>

        <div>
          <span className="text-sm font-medium text-slate-700">Upload a file</span>
          <input
            ref={fileInputRef}
            type="file"
            accept=".csv,.txt,text/csv,text/plain"
            onChange={handleFile}
            className="mt-2 block w-full text-sm text-slate-600 file:mr-3 file:rounded-xl file:border-0 file:bg-slate-100 file:px-4 file:py-2 file:text-slate-700 file:hover:bg-slate-200"
          />
        </div>

        <label className="block">
          <span className="text-sm font-medium text-slate-700">Or paste CSV</span>
          <textarea
            value={text}
            onChange={(e) => {
              setText(e.target.value);
              setError(null);
            }}
            placeholder={"correr,to run,verb\nolor,smell,noun\ndulce,sweet,adjective"}
            rows={6}
            className="mt-1 w-full rounded-xl border border-slate-200 px-4 py-2.5 font-mono text-sm focus:outline-none focus:ring-2 focus:ring-brand-400"
          />
        </label>

        <div className="flex items-center justify-between text-sm">
          <span className="text-slate-500">
            {parsed.length} row{parsed.length === 1 ? "" : "s"} ready to import
          </span>
          {error && <span className="text-rose-600">{error}</span>}
        </div>

        <div className="flex justify-end gap-2 pt-2">
          <button
            type="button"
            onClick={handleClose}
            className="px-4 py-2 rounded-xl text-slate-600 hover:bg-slate-100 transition"
          >
            Cancel
          </button>
          <button
            type="button"
            onClick={handleImport}
            disabled={parsed.length === 0}
            className="px-5 py-2 rounded-xl bg-btn-purple text-white font-medium shadow-soft hover:brightness-110 disabled:opacity-50 disabled:cursor-not-allowed transition"
          >
            Import {parsed.length || ""}
          </button>
        </div>
      </div>
    </Modal>
  );
}
