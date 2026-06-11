"use client";

import Link from "next/link";
import { useMemo, useState } from "react";
import { getVocabProperty } from "@/lib/vocab-properties";
import type { VocabItem } from "@/lib/types";
import type { VocabGroup, VocabViewConfig } from "@/lib/vocab-view";
import { groupVocab } from "@/lib/vocab-view";

function BoardCard({
  item,
  groupBy,
  onDragStart,
}: {
  item: VocabItem;
  groupBy: string;
  onDragStart: () => void;
}) {
  const translation = item.glossPrimary || item.translation;
  return (
    <div
      draggable
      onDragStart={onDragStart}
      className="rounded-xl border border-slate-200 bg-white p-3 shadow-sm cursor-grab active:cursor-grabbing hover:border-brand-200 transition"
    >
      <Link
        href={`/words/${item.id}`}
        className="font-medium text-slate-900 hover:text-brand-700"
        onClick={(e) => e.stopPropagation()}
      >
        {item.word}
      </Link>
      <p className="text-sm text-slate-500 mt-0.5">{translation}</p>
      {groupBy !== "tags" && item.tags[0] && (
        <span className="mt-2 inline-block text-xs px-2 py-0.5 rounded-full bg-slate-100 text-slate-600 capitalize">
          {item.tags[0]}
        </span>
      )}
      {item.enriching && (
        <span className="mt-2 block text-xs text-amber-600">enriching…</span>
      )}
    </div>
  );
}

export function VocabBoardView({
  items,
  config,
  loading,
  onUpdateField,
}: {
  items: VocabItem[];
  config: VocabViewConfig;
  loading: boolean;
  onUpdateField: (
    id: number,
    field: string,
    value: string | boolean,
  ) => void;
}) {
  const groupBy = config.groupBy ?? "learned";
  const prop = getVocabProperty(groupBy);
  const writable = prop?.writable ?? false;

  const groups = useMemo(() => {
    const grouped = groupVocab(items, groupBy);
    if (grouped) return grouped;
    return [{ key: "", label: "All", items }];
  }, [items, groupBy]);

  const [draggingId, setDraggingId] = useState<number | null>(null);

  function handleDrop(group: VocabGroup) {
    if (draggingId == null || !writable) return;
    if (groupBy === "learned") {
      onUpdateField(draggingId, "learned", group.key === "true");
    } else if (groupBy === "cefr") {
      onUpdateField(draggingId, "cefr", group.key || "");
    }
    setDraggingId(null);
  }

  if (loading) {
    return (
      <div className="glass-card rounded-2xl p-12 text-center text-slate-400">
        Loading…
      </div>
    );
  }

  return (
    <div className="flex gap-4 overflow-x-auto pb-2">
      {groups.map((group) => (
        <div
          key={group.key || "empty"}
          className="min-w-[240px] flex-1 glass-card rounded-2xl p-3 flex flex-col gap-2"
          onDragOver={(e) => {
            if (writable) e.preventDefault();
          }}
          onDrop={() => handleDrop(group)}
        >
          <div className="flex items-center justify-between px-1 pb-2 border-b border-slate-100">
            <h3 className="text-sm font-semibold text-slate-700">
              {group.label}
            </h3>
            <span className="text-xs text-slate-400">{group.items.length}</span>
          </div>
          <div className="flex flex-col gap-2 min-h-[120px]">
            {group.items.length === 0 ? (
              <p className="text-xs text-slate-400 text-center py-8">
                {writable ? "Drop words here" : "Empty"}
              </p>
            ) : (
              group.items.map((item) => (
                <BoardCard
                  key={item.id}
                  item={item}
                  groupBy={groupBy}
                  onDragStart={() => setDraggingId(item.id)}
                />
              ))
            )}
          </div>
        </div>
      ))}
      {!writable && (
        <p className="text-xs text-slate-400 self-end pb-2">
          Group by learned or CEFR to drag cards between columns.
        </p>
      )}
    </div>
  );
}
