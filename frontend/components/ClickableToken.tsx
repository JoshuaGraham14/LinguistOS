"use client";

import { useEffect, useRef, useState } from "react";
import { cn } from "@/lib/cn";
import type { AtomRef } from "@/lib/types";
import { WordActionPopover } from "./WordActionPopover";

interface ClickableTokenProps {
  atom: AtomRef;
}

export function ClickableToken({ atom }: ClickableTokenProps) {
  const [open, setOpen] = useState(false);
  const rootRef = useRef<HTMLSpanElement>(null);

  useEffect(() => {
    if (!open) return;
    function onDocClick(event: MouseEvent) {
      const root = rootRef.current;
      if (!root) return;
      if (!root.contains(event.target as Node)) setOpen(false);
    }
    document.addEventListener("mousedown", onDocClick);
    return () => document.removeEventListener("mousedown", onDocClick);
  }, [open]);

  const known = typeof atom.vocabId === "number";

  return (
    <span ref={rootRef} className="relative inline-block">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        className={cn(
          "rounded px-0.5 transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-brand-400",
          known
            ? "text-brand-700 hover:bg-brand-100/60"
            : "text-amber-800 hover:bg-amber-100/70",
        )}
        title={known ? "Known word" : "Unknown word"}
      >
        {atom.surfaceToken}
      </button>
      {open && <WordActionPopover atom={atom} onClose={() => setOpen(false)} />}
    </span>
  );
}
