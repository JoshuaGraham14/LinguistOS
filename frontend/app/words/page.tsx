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
} from "lucide-react";
import { useEffect, useMemo, useRef, useState } from "react";
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

interface WordFormValues {
  word: string;
  translation: string;
  tags: VocabTag[];
}

export default function WordsPage() {
  const { vocab, hydrated, addVocab, removeVocab, updateVocab } = useVocab();
  const [search, setSearch] = useState("");
  const [activeTags, setActiveTags] = useState<VocabTag[]>([]);
  const [sort, setSort] = useState<SortOrder>("newest");
  const [sortOpen, setSortOpen] = useState(false);
  const [addOpen, setAddOpen] = useState(false);
  const [importOpen, setImportOpen] = useState(false);
  const [editing, setEditing] = useState<VocabItem | null>(null);

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
            onClick={() => setImportOpen(true)}
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
            <WordCard
              key={v.id}
              item={v}
              onDelete={() => removeVocab(v.id)}
              onEdit={() => setEditing(v)}
            />
          ))}
        </section>
      )}

      <WordFormModal
        open={addOpen}
        onClose={() => setAddOpen(false)}
        title="Add a word"
        submitLabel="Add word"
        onSubmit={(values) => addVocab(values)}
      />
      <WordFormModal
        open={editing !== null}
        onClose={() => setEditing(null)}
        title="Edit word"
        submitLabel="Save changes"
        initial={editing}
        onSubmit={(values) => {
          if (editing) updateVocab(editing.id, values);
        }}
      />
      <ImportWordsModal
        open={importOpen}
        onClose={() => setImportOpen(false)}
        onImport={(rows) => {
          rows.forEach((r) => addVocab(r));
        }}
      />
    </div>
  );
}

function WordCard({
  item,
  onDelete,
  onEdit,
}: {
  item: VocabItem;
  onDelete: () => void;
  onEdit: () => void;
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
          onClick={onEdit}
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

function WordFormModal({
  open,
  onClose,
  onSubmit,
  title,
  submitLabel,
  initial,
}: {
  open: boolean;
  onClose: () => void;
  onSubmit: (input: WordFormValues) => void;
  title: string;
  submitLabel: string;
  initial?: VocabItem | null;
}) {
  const [word, setWord] = useState(initial?.word ?? "");
  const [translation, setTranslation] = useState(initial?.translation ?? "");
  const [tags, setTags] = useState<VocabTag[]>(initial?.tags ?? []);

  useEffect(() => {
    if (!open) return;
    setWord(initial?.word ?? "");
    setTranslation(initial?.translation ?? "");
    setTags(initial?.tags ?? []);
  }, [open, initial?.id, initial?.word, initial?.translation, initial?.tags]);

  function toggleTag(tag: VocabTag) {
    setTags((t) =>
      t.includes(tag) ? t.filter((x) => x !== tag) : [...t, tag],
    );
  }

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!word.trim() || !translation.trim()) return;
    onSubmit({ word: word.trim(), translation: translation.trim(), tags });
    onClose();
  }

  return (
    <Modal open={open} onClose={onClose} title={title}>
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
            {submitLabel}
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
