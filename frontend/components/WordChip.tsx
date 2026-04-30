"use client";

import Link from "next/link";
import { usePathname, useSearchParams } from "next/navigation";
import { useMemo } from "react";
import { cn } from "@/lib/cn";
import { formatWordDisplay, useProfile, useVocab } from "@/lib/storage";
import type { VocabItem, WordRef } from "@/lib/types";

interface WordChipProps {
  /**
   * Either a ``WordRef`` (preferred) or a fully-resolved ``VocabItem``.
   * Either way the chip renders via the canonical ``formatWordDisplay``
   * helper so a single edit to the lemma propagates everywhere (LOS-104).
   */
  wordRef?: WordRef;
  item?: VocabItem;
  /** Render compact (no gloss tooltip footer). */
  compact?: boolean;
  /** Override the navigation target. Defaults to the Word Home page. */
  href?: string;
  className?: string;
}

export function WordChip({
  wordRef,
  item,
  compact = false,
  href,
  className,
}: WordChipProps) {
  const { vocab } = useVocab();
  const { profile } = useProfile();
  const pathname = usePathname();
  const searchParams = useSearchParams();

  const resolved = useMemo<VocabItem | null>(() => {
    if (item) return item;
    if (!wordRef) return null;
    return vocab.find((v) => v.id === wordRef.vocabId) ?? null;
  }, [item, wordRef, vocab]);

  if (!resolved) {
    const fallback = wordRef ? `#${wordRef.vocabId}` : "?";
    return (
      <span
        className={cn(
          "inline-flex items-center rounded-md px-1.5 py-0.5 bg-slate-100 text-slate-500 text-sm",
          className,
        )}
      >
        {fallback}
      </span>
    );
  }

  const display = formatWordDisplay(resolved, profile.wordDisplayMode);
  const target = useMemo(() => {
    if (href) return href;
    const next = new URLSearchParams(searchParams.toString());
    next.set("word_quick", String(resolved.id));
    const q = next.toString();
    return q ? `${pathname}?${q}` : pathname;
  }, [href, pathname, resolved.id, searchParams]);
  const tooltip = resolved.glossPrimary || resolved.translation || "";
  const showGloss = !compact && Boolean(tooltip);

  return (
    <Link
      href={target}
      title={tooltip}
      className={cn(
        "inline-flex items-baseline gap-1 rounded-md px-1.5 py-0.5",
        "bg-brand-50 text-brand-700 hover:bg-brand-100 transition",
        "decoration-dotted underline-offset-2",
        className,
      )}
    >
      <span className="font-medium">{display.primary}</span>
      {showGloss && (
        <span className="text-xs text-brand-600/70">{tooltip}</span>
      )}
    </Link>
  );
}
