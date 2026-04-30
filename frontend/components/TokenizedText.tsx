"use client";

import { useEffect, useMemo, useState } from "react";
import { resolveTokens } from "@/lib/api";
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
  const { vocab, activeWorkspace } = useVocab();
  const [resolved, setResolved] = useState<
    Array<{
      token: string;
      vocabId?: number;
      candidates?: AtomRef["candidates"];
    }>
  >([]);

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

  useEffect(() => {
    if (!activeWorkspace || !text.trim()) {
      setResolved([]);
      return;
    }
    let cancelled = false;
    const timer = window.setTimeout(async () => {
      try {
        const spans = await resolveTokens({
          workspaceId: activeWorkspace.id,
          language,
          text,
        });
        if (cancelled) return;
        setResolved(
          spans.map((s) => ({
            token: s.token,
            vocabId: s.vocab_id ?? undefined,
            candidates: s.candidates.map((c) => ({
              vocabId: c.vocab_id,
              word: c.word,
              lemma: c.lemma ?? undefined,
              translation: c.translation,
            })),
          })),
        );
      } catch {
        if (!cancelled) setResolved([]);
      }
    }, 120);
    return () => {
      cancelled = true;
      window.clearTimeout(timer);
    };
  }, [activeWorkspace, language, text]);

  return (
    <span className={className}>
      {(() => {
        let wordIndex = 0;
        let resolvedIndex = 0;
        return parts.map((part, idx) => {
          if (!part.isWord) return <span key={`sep-${idx}`}>{part.text}</span>;
          const key = normalizeToken(part.text);
          wordIndex += 1;

          // Resolve spans can occasionally drift from local tokenization for
          // edge punctuation/forms. Align defensively by normalized token.
          let remote:
            | {
                token: string;
                vocabId?: number;
                candidates?: AtomRef["candidates"];
              }
            | undefined = resolved[resolvedIndex];
          if (remote) {
            const remoteNorm = normalizeToken(remote.token);
            if (remoteNorm === key) {
              resolvedIndex += 1;
            } else {
              const lookahead = resolved
                .slice(resolvedIndex + 1, resolvedIndex + 4)
                .find((r) => normalizeToken(r.token) === key);
              if (lookahead) {
                remote = lookahead;
                resolvedIndex = resolved.findIndex((r, i) => i >= resolvedIndex && r === lookahead) + 1;
              } else {
                remote = undefined;
              }
            }
          }
          const atom: AtomRef = {
            vocabId: remote?.vocabId ?? lookup.get(key),
            candidates: remote?.candidates,
            surfaceToken: part.text,
            language,
            sourceContext,
          };
          return <ClickableToken key={`tok-${idx}-${part.text}`} atom={atom} />;
        });
      })()}
    </span>
  );
}
