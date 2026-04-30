"use client";

import { useRef } from "react";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { tokenAction } from "@/lib/api";
import { cn } from "@/lib/cn";
import type { AtomRef } from "@/lib/types";
import { trackTokenMetric } from "@/lib/tokenTelemetry";
import { useVocab } from "@/lib/storage";

interface ClickableTokenProps {
  atom: AtomRef;
}

export function ClickableToken({ atom }: ClickableTokenProps) {
  const { activeWorkspace } = useVocab();
  const rootRef = useRef<HTMLSpanElement>(null);
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();

  const known = typeof atom.vocabId === "number";

  return (
    <span ref={rootRef} className="relative inline-block">
      <button
        type="button"
        onClick={() => {
          trackTokenMetric("token_click");
          if (activeWorkspace && atom.vocabId) {
            void tokenAction({
              action: "record_occurrence",
              workspaceId: activeWorkspace.id,
              language: atom.language,
              token: atom.surfaceToken,
              vocabId: atom.vocabId,
              contextType: atom.sourceContext.type,
              contextId: atom.sourceContext.id != null ? String(atom.sourceContext.id) : undefined,
              source: "token_click",
            });
          }
          const next = new URLSearchParams(searchParams.toString());
          if (typeof atom.vocabId === "number") {
            next.set("word_quick", String(atom.vocabId));
            next.delete("word_surface");
          } else {
            next.delete("word_quick");
            next.set("word_surface", atom.surfaceToken);
          }
          const query = next.toString();
          router.replace(query ? `${pathname}?${query}` : pathname, { scroll: false });
          window.dispatchEvent(
            new CustomEvent("linguistos:open-word-panel", {
              detail: { source: "token", known: typeof atom.vocabId === "number" },
            }),
          );
        }}
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
    </span>
  );
}
