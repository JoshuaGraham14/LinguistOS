"use client";

import {
  BookOpen,
  Calendar,
  Check,
  MessageSquare,
  Pencil,
  Trash2,
} from "lucide-react";
import Link from "next/link";
import { cn } from "@/lib/cn";
import { getVocabProperty } from "@/lib/vocab-properties";
import type { VocabItem, VocabTag } from "@/lib/types";
import type { VocabViewConfig } from "@/lib/vocab-view";
import { orderedVisibleProperties } from "@/lib/vocab-view";

const TAG_COLORS: Record<VocabTag, string> = {
  noun: "bg-blue-100 text-blue-700",
  verb: "bg-emerald-100 text-emerald-700",
  adjective: "bg-amber-100 text-amber-700",
  adverb: "bg-pink-100 text-pink-700",
  preposition: "bg-indigo-100 text-indigo-700",
  other: "bg-slate-100 text-slate-700",
};

function formatDate(ts: number) {
  return new Date(ts).toLocaleDateString("en-GB");
}

function GalleryField({
  item,
  propertyKey,
}: {
  item: VocabItem;
  propertyKey: string;
}) {
  switch (propertyKey) {
    case "word":
      return (
        <div className="text-3xl font-bold text-slate-900 text-right break-words">
          <Link href={`/words/${item.id}`} className="hover:text-brand-700">
            {item.word}
          </Link>
        </div>
      );
    case "translation":
      return (
        <div className="text-slate-600">
          {item.glossPrimary || item.translation}
        </div>
      );
    case "tags":
      return (
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
      );
    case "learned":
      return (
        <span className={item.learned ? "text-emerald-600 text-sm" : "text-slate-500 text-sm"}>
          {item.learned ? "Learned" : "Still learning"}
        </span>
      );
    case "cefr":
      return item.cefr ? (
        <span className="text-sm text-slate-600">CEFR {item.cefr}</span>
      ) : null;
    case "createdAt":
      return (
        <div className="flex items-center gap-1.5 text-xs text-slate-500">
          <Calendar className="h-3.5 w-3.5" strokeWidth={2} />
          {formatDate(item.createdAt)}
        </div>
      );
    default: {
      const prop = getVocabProperty(propertyKey);
      if (!prop) return null;
      const val = prop.getValue(item);
      if (val == null || val === "") return null;
      return <span className="text-sm text-slate-600">{String(val)}</span>;
    }
  }
}

function GalleryCard({
  item,
  fields,
  onEdit,
  onDelete,
  onToggleLearned,
}: {
  item: VocabItem;
  fields: string[];
  onEdit: () => void;
  onDelete: () => void;
  onToggleLearned: () => void;
}) {
  const showLearnedToggle = fields.includes("learned");

  return (
    <div
      className={cn(
        "glass-card rounded-2xl p-6 flex flex-col gap-4 group transition",
        item.learned && "ring-2 ring-emerald-300/60",
      )}
    >
      <div className="flex items-start justify-between gap-2">
        {showLearnedToggle ? (
          <button
            type="button"
            onClick={onToggleLearned}
            className={cn(
              "h-7 px-3 rounded-full text-xs font-medium transition inline-flex items-center gap-1",
              item.learned
                ? "bg-emerald-500 text-white hover:bg-emerald-600"
                : "bg-slate-100 text-slate-500 hover:bg-slate-200",
            )}
          >
            <Check className="h-3 w-3" strokeWidth={3} />
            {item.learned ? "Learned" : "Mark learned"}
          </button>
        ) : (
          <span />
        )}
        {fields.includes("word") && (
          <GalleryField item={item} propertyKey="word" />
        )}
      </div>

      {fields
        .filter((k) => k !== "word" && k !== "learned")
        .map((key) => (
          <GalleryField key={key} item={item} propertyKey={key} />
        ))}

      {item.enriching && (
        <span className="text-xs px-2 py-0.5 rounded-full bg-amber-50 text-amber-700 w-fit">
          enriching…
        </span>
      )}

      <div className="flex items-center gap-2 mt-auto">
        <Link
          href={`/learn/sentences?word=${item.id}`}
          className="h-9 px-3 rounded-full bg-fuchsia-500 text-white text-xs font-medium flex items-center gap-1 hover:bg-fuchsia-600 transition shadow-soft"
        >
          <MessageSquare className="h-3.5 w-3.5" strokeWidth={2.5} />
          Sentences
        </Link>
        <Link
          href={`/learn/flashcards?word=${item.id}`}
          className="h-9 px-3 rounded-full bg-blue-500 text-white text-xs font-medium flex items-center gap-1 hover:bg-blue-600 transition shadow-soft"
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
    </div>
  );
}

export function VocabGalleryView({
  items,
  config,
  loading,
  onEdit,
  onDelete,
  onToggleLearned,
}: {
  items: VocabItem[];
  config: VocabViewConfig;
  loading: boolean;
  onEdit: (item: VocabItem) => void;
  onDelete: (id: number) => void;
  onToggleLearned: (id: number) => void;
}) {
  const fields = orderedVisibleProperties(config);

  if (loading) {
    return (
      <div className="glass-card rounded-2xl p-12 text-center text-slate-400">
        Loading…
      </div>
    );
  }

  if (items.length === 0) {
    return (
      <div className="glass-card rounded-2xl p-12 text-center text-slate-500">
        No words match this view.
      </div>
    );
  }

  return (
    <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
      {items.map((item) => (
        <GalleryCard
          key={item.id}
          item={item}
          fields={fields}
          onEdit={() => onEdit(item)}
          onDelete={() => onDelete(item.id)}
          onToggleLearned={() => onToggleLearned(item.id)}
        />
      ))}
    </div>
  );
}
