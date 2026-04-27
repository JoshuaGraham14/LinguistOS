"use client";

import {
  Calendar,
  ChevronDown,
  Pencil,
  Plus,
  Search,
  SlidersHorizontal,
  Trash2,
  Upload,
  Volume2,
  VolumeX,
} from "lucide-react";
import { useMemo, useState } from "react";
import { Modal } from "@/components/Modal";
import { cn } from "@/lib/cn";
import { useVocab } from "@/lib/storage";
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

const SORT_LABELS: Record<SortOrder, string> = {
  newest: "Newest First",
  oldest: "Oldest First",
  alpha: "Alphabetical",
};

function formatDate(ts: number) {
  return new Date(ts).toLocaleDateString("en-GB");
}

export default function WordsPage() {
  const { vocab, hydrated, addVocab, removeVocab } = useVocab();
  const [search, setSearch] = useState("");
  const [activeTags, setActiveTags] = useState<VocabTag[]>([]);
  const [sort, setSort] = useState<SortOrder>("newest");
  const [sortOpen, setSortOpen] = useState(false);
  const [addOpen, setAddOpen] = useState(false);

  function toggleActiveTag(tag: VocabTag) {
    setActiveTags((t) =>
      t.includes(tag) ? t.filter((x) => x !== tag) : [...t, tag],
    );
  }

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
    const sorted = [...list];
    if (sort === "newest") sorted.sort((a, b) => b.createdAt - a.createdAt);
    else if (sort === "oldest") sorted.sort((a, b) => a.createdAt - b.createdAt);
    else sorted.sort((a, b) => a.word.localeCompare(b.word));
    return sorted;
  }, [vocab, search, activeTags, sort]);

  return (
    <div className="space-y-6">
      <header className="flex items-start justify-between gap-4">
        <div>
          <h1 className="text-3xl font-bold text-slate-900">My Word Collection</h1>
          <p className="text-slate-500 mt-1">Manage your Spanish vocabulary</p>
        </div>
        <div className="flex gap-3">
          <button
            type="button"
            className="inline-flex items-center gap-2 rounded-xl bg-gradient-to-r from-blue-500 to-blue-600 text-white font-medium px-5 py-3 shadow-soft hover:brightness-110 transition"
          >
            <Upload className="h-4 w-4" strokeWidth={2.5} />
            Import Words
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

      <section className="rounded-2xl bg-white/80 backdrop-blur shadow-card p-5 space-y-4">
        <div className="relative">
          <Search className="absolute left-4 top-1/2 -translate-y-1/2 h-5 w-5 text-slate-400" />
          <input
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search Spanish or English..."
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
                className="absolute right-0 top-full mt-1 w-44 rounded-xl bg-white shadow-card border border-slate-100 py-1 z-10"
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
            <WordCard key={v.id} item={v} onDelete={() => removeVocab(v.id)} />
          ))}
        </section>
      )}

      <AddWordModal open={addOpen} onClose={() => setAddOpen(false)} onAdd={addVocab} />
    </div>
  );
}

function WordCard({
  item,
  onDelete,
}: {
  item: VocabItem;
  onDelete: () => void;
}) {
  return (
    <div className="rounded-2xl bg-white/90 shadow-card p-6 flex flex-col gap-4 group">
      <div className="text-3xl font-bold text-slate-900 text-right">
        {item.word}
      </div>
      <div className="text-slate-600">{item.translation}</div>

      <div className="flex items-center gap-2">
        <button
          type="button"
          className="h-9 w-9 rounded-full bg-blue-500 text-white flex items-center justify-center hover:bg-blue-600 transition shadow-soft"
          aria-label="Play audio"
        >
          <Volume2 className="h-4 w-4" strokeWidth={2.5} />
        </button>
        <button
          type="button"
          className="h-9 w-9 rounded-full bg-emerald-500 text-white flex items-center justify-center hover:bg-emerald-600 transition shadow-soft"
          aria-label="Slow audio"
        >
          <VolumeX className="h-4 w-4" strokeWidth={2.5} />
        </button>
        <button
          type="button"
          className="h-9 w-9 rounded-full bg-amber-500 text-white flex items-center justify-center hover:bg-amber-600 transition shadow-soft"
          aria-label="Edit"
        >
          <Pencil className="h-4 w-4" strokeWidth={2.5} />
        </button>
        <button
          type="button"
          onClick={onDelete}
          className="ml-auto p-2 rounded-lg text-slate-300 hover:text-rose-500 hover:bg-rose-50 transition opacity-0 group-hover:opacity-100"
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
          item.tags.map((t) => (
            <span
              key={t}
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

function AddWordModal({
  open,
  onClose,
  onAdd,
}: {
  open: boolean;
  onClose: () => void;
  onAdd: (input: { word: string; translation: string; tags: VocabTag[] }) => void;
}) {
  const [word, setWord] = useState("");
  const [translation, setTranslation] = useState("");
  const [tags, setTags] = useState<VocabTag[]>([]);

  function toggleTag(tag: VocabTag) {
    setTags((t) =>
      t.includes(tag) ? t.filter((x) => x !== tag) : [...t, tag],
    );
  }

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!word.trim() || !translation.trim()) return;
    onAdd({ word: word.trim(), translation: translation.trim(), tags });
    setWord("");
    setTranslation("");
    setTags([]);
    onClose();
  }

  return (
    <Modal open={open} onClose={onClose} title="Add a word">
      <form onSubmit={handleSubmit} className="space-y-4">
        <label className="block">
          <span className="text-sm font-medium text-slate-700">Spanish</span>
          <input
            value={word}
            onChange={(e) => setWord(e.target.value)}
            placeholder="e.g. correr"
            autoFocus
            className="mt-1 w-full rounded-xl border border-slate-200 px-4 py-2.5 focus:outline-none focus:ring-2 focus:ring-brand-400"
          />
        </label>
        <label className="block">
          <span className="text-sm font-medium text-slate-700">English</span>
          <input
            value={translation}
            onChange={(e) => setTranslation(e.target.value)}
            placeholder="e.g. to run"
            className="mt-1 w-full rounded-xl border border-slate-200 px-4 py-2.5 focus:outline-none focus:ring-2 focus:ring-brand-400"
          />
        </label>
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
            disabled={!word.trim() || !translation.trim()}
            className="px-5 py-2 rounded-xl bg-btn-purple text-white font-medium shadow-soft hover:brightness-110 disabled:opacity-50 disabled:cursor-not-allowed transition"
          >
            Add word
          </button>
        </div>
      </form>
    </Modal>
  );
}
