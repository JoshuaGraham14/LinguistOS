"use client";

import { useMemo } from "react";
import { normalizeToken, splitIntoTokenParts } from "@/lib/tokenize";
import { useVocab } from "@/lib/storage";
import type { AtomRef, LanguageCode } from "@/lib/types";
import { ClickableToken } from "./ClickableToken";

interface TokenizedTextProps {
  text: string;
  language: LanguageCode;
  sourceContext: AtomRef["sourceContext"];
  className?: string;
}

export function TokenizedText({
  text,
  language,
  sourceContext,
  className,
}: TokenizedTextProps) {
  const { vocab } = useVocab();

  const lookup = useMemo(() => {
    const m = new Map<string, number>();
    for (const v of vocab) {
      if (v.language !== language) continue;
      const forms = [v.word, v.lemma ?? "", v.surfaceForm ?? "", ...(v.surfaceForms ?? [])];
      for (const f of forms) {
        const key = normalizeToken(f);
        if (key && !m.has(key)) m.set(key, v.id);
      }
    }
    return m;
  }, [vocab, language]);

  const parts = useMemo(() => splitIntoTokenParts(text), [text]);

  return (
    <span className={className}>
      {parts.map((part, idx) => {
        if (!part.isWord) return <span key={`sep-${idx}`}>{part.text}</span>;
        const key = normalizeToken(part.text);
        const atom: AtomRef = {
          vocabId: lookup.get(key),
          surfaceToken: part.text,
          language,
          sourceContext,
        };
        return <ClickableToken key={`tok-${idx}-${part.text}`} atom={atom} />;
      })}
    </span>
  );
}
