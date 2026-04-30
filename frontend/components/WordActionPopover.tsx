"use client";

import Link from "next/link";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { useMemo, useState } from "react";
import { useVocab } from "@/lib/storage";
import type { AtomRef } from "@/lib/types";

interface WordActionPopoverProps {
  atom: AtomRef;
  onClose: () => void;
}

export function WordActionPopover({ atom, onClose }: WordActionPopoverProps) {
  const { addVocab } = useVocab();
  const [loading, setLoading] = useState(false);
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();

  const known = typeof atom.vocabId === "number";

  const quickViewHref = useMemo(() => {
    if (!known) return "#";
    const next = new URLSearchParams(searchParams.toString());
    next.set("word_quick", String(atom.vocabId));
    const q = next.toString();
    return q ? `${pathname}?${q}` : pathname;
  }, [atom.vocabId, known, pathname, searchParams]);

  async function handleAdd() {
    if (loading || known) return;
    setLoading(true);
    try {
      const item = await addVocab({ surfaceForm: atom.surfaceToken });
      const next = new URLSearchParams(searchParams.toString());
      next.set("word_quick", String(item.id));
      const q = next.toString();
      router.replace(q ? `${pathname}?${q}` : pathname, { scroll: false });
      onClose();
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="absolute z-40 mt-2 w-64 rounded-xl border border-slate-200 bg-white shadow-2xl p-2">
      {known ? (
        <div className="space-y-1">
          <Link
            href={quickViewHref}
            onClick={onClose}
            className="block rounded-lg px-3 py-2 text-sm text-slate-700 hover:bg-slate-100"
          >
            Open word quick view
          </Link>
          <Link
            href={`/learn/flashcards?word=${atom.vocabId}`}
            onClick={onClose}
            className="block rounded-lg px-3 py-2 text-sm text-slate-700 hover:bg-slate-100"
          >
            Practice in flashcards
          </Link>
          <Link
            href={`/learn/sentences?word=${atom.vocabId}`}
            onClick={onClose}
            className="block rounded-lg px-3 py-2 text-sm text-slate-700 hover:bg-slate-100"
          >
            Practice in sentences
          </Link>
        </div>
      ) : (
        <div className="space-y-2">
          <button
            type="button"
            onClick={handleAdd}
            disabled={loading}
            className="w-full rounded-lg bg-btn-purple text-white text-sm font-medium px-3 py-2 hover:brightness-110 disabled:opacity-60"
          >
            {loading ? "Adding..." : `Add “${atom.surfaceToken}” to word bank`}
          </button>
          <button
            type="button"
            onClick={onClose}
            className="w-full rounded-lg border border-slate-200 text-slate-600 text-sm px-3 py-2 hover:bg-slate-50"
          >
            Dismiss
          </button>
        </div>
      )}
    </div>
  );
}
