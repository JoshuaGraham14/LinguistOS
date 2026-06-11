"use client";

import {
  ArrowDown,
  ArrowUp,
  ArrowUpDown,
  MessageSquare,
} from "lucide-react";
import Link from "next/link";
import { cn } from "@/lib/cn";
import { formatWordDisplay } from "@/lib/storage";
import type {
  SortDirection,
  SortRule,
  VocabItem,
  WordDisplayMode,
} from "@/lib/types";
import { getVocabProperty } from "@/lib/vocab-properties";
import type { VocabViewConfig } from "@/lib/vocab-view";
import { orderedVisibleProperties } from "@/lib/vocab-view";

function formatDate(ts: number | null) {
  if (!ts) return "—";
  return new Date(ts).toLocaleDateString("en-GB");
}

function sortIcon(
  field: string,
  sorts: SortRule[],
): "asc" | "desc" | null {
  const rule = sorts.find((s) => s.field === field);
  return rule?.direction ?? null;
}

function PropertyCell({
  item,
  propertyKey,
  mode,
}: {
  item: VocabItem;
  propertyKey: string;
  mode: WordDisplayMode;
}) {
  const display = formatWordDisplay(item, mode);
  switch (propertyKey) {
    case "word":
      return (
        <div>
          <Link href={`/words/${item.id}`} className="hover:text-brand-700 font-medium text-slate-900">
            {display.primary}
          </Link>
          {display.secondary && (
            <div className="text-xs text-slate-400">{display.secondary}</div>
          )}
        </div>
      );
    case "lemma":
      return <span className="text-slate-700">{item.lemma ?? item.word}</span>;
    case "translation":
      return (
        <span className="text-slate-700">
          {item.glossPrimary || item.translation}
        </span>
      );
    case "pos":
      return (
        <span className="text-slate-600 capitalize">{item.pos ?? "—"}</span>
      );
    case "cefr":
      return <span className="text-slate-600">{item.cefr ?? "—"}</span>;
    case "tags":
      return (
        <div className="flex flex-wrap gap-1">
          {item.enriching && (
            <span className="text-xs px-2 py-0.5 rounded-full bg-amber-50 text-amber-700">
              enriching…
            </span>
          )}
          {item.tags.length === 0 ? (
            <span className="text-xs text-slate-400">—</span>
          ) : (
            item.tags.map((t, i) => (
              <span
                key={`${item.id}-${t}-${i}`}
                className="text-xs px-2 py-0.5 rounded-full bg-slate-100 text-slate-600 capitalize"
              >
                {t}
              </span>
            ))
          )}
        </div>
      );
    case "box":
      return <span className="text-slate-700">{item.mastery?.box ?? 0}</span>;
    case "nextDue":
      return (
        <span className="text-slate-600">
          {formatDate(item.mastery?.nextDue ?? null)}
        </span>
      );
    case "learned":
      return (
        <span className={item.learned ? "text-emerald-600" : "text-slate-500"}>
          {item.learned ? "Yes" : "No"}
        </span>
      );
    case "gender":
      return <span className="text-slate-600">{item.gender ?? "—"}</span>;
    case "ipa":
      return <span className="text-slate-600 font-mono text-xs">{item.ipa ?? "—"}</span>;
    case "createdAt":
      return (
        <span className="text-slate-600">{formatDate(item.createdAt)}</span>
      );
    default:
      return <span className="text-slate-400">—</span>;
  }
}

export function VocabTableView({
  items,
  config,
  loading,
  wordDisplayMode,
  onSort,
}: {
  items: VocabItem[];
  config: VocabViewConfig;
  loading: boolean;
  wordDisplayMode: WordDisplayMode;
  onSort: (field: string) => void;
}) {
  const columns = orderedVisibleProperties(config);
  const colSpan = columns.length + 1;

  return (
    <section className="glass-card rounded-2xl overflow-hidden flex-1 min-h-0">
      <div className="overflow-x-auto">
        <table className="min-w-full text-sm">
          <thead className="bg-slate-50 text-slate-500 uppercase text-xs tracking-wide">
            <tr>
              {columns.map((key) => {
                const prop = getVocabProperty(key);
                const active = sortIcon(key, config.sorts);
                return (
                  <th key={key} className="px-4 py-2 text-left">
                    {prop?.sortable ? (
                      <button
                        type="button"
                        onClick={() => onSort(key)}
                        className="inline-flex items-center gap-1 hover:text-slate-700"
                      >
                        {prop.label}
                        {active === "asc" ? (
                          <ArrowUp className="h-3 w-3" />
                        ) : active === "desc" ? (
                          <ArrowDown className="h-3 w-3" />
                        ) : (
                          <ArrowUpDown className="h-3 w-3 opacity-40" />
                        )}
                      </button>
                    ) : (
                      prop?.label ?? key
                    )}
                  </th>
                );
              })}
              <th className="px-4 py-2" />
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {loading ? (
              <tr>
                <td colSpan={colSpan} className="px-4 py-12 text-center text-slate-400">
                  Loading…
                </td>
              </tr>
            ) : items.length === 0 ? (
              <tr>
                <td colSpan={colSpan} className="px-4 py-12 text-center text-slate-500">
                  No words match this view.
                </td>
              </tr>
            ) : (
              items.map((item) => (
                <tr key={item.id} className="hover:bg-slate-50/50">
                  {columns.map((key) => (
                    <td key={key} className="px-4 py-2">
                      <PropertyCell
                        item={item}
                        propertyKey={key}
                        mode={wordDisplayMode}
                      />
                    </td>
                  ))}
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
              ))
            )}
          </tbody>
        </table>
      </div>
    </section>
  );
}

export function toggleSortRule(
  sorts: SortRule[],
  field: string,
): SortRule[] {
  const existing = sorts.find((s) => s.field === field);
  if (!existing) return [{ field, direction: "asc" }];
  if (existing.direction === "asc") {
    return sorts.map((s) =>
      s.field === field ? { ...s, direction: "desc" as SortDirection } : s,
    );
  }
  return sorts.filter((s) => s.field !== field);
}
