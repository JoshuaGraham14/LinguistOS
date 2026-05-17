import {
  enrichVocabSuggestion,
  type VocabDraft,
  type VocabSuggestion,
  type VocabSuggestDirection,
  type VocabSuggestResult,
} from "@/lib/api";

export type VocabFieldSwapHint = {
  message: string;
  otherField: "target" | "english";
};

const LANGUAGE_LABELS: Record<string, string> = {
  es: "Spanish",
  fr: "French",
  he: "Hebrew",
};

export function fieldSwapHint(
  attemptedDirection: VocabSuggestDirection,
  languageCode: string,
): VocabFieldSwapHint {
  const language =
    LANGUAGE_LABELS[languageCode.toLowerCase()] ?? languageCode.toUpperCase();
  if (attemptedDirection === "target-to-en") {
    return {
      message: "Looks like English? We moved it and filled the translation.",
      otherField: "english",
    };
  }
  return {
    message: `Looks like ${language}? We moved it and filled the translation.`,
    otherField: "target",
  };
}

export async function applyAutoSwappedSuggestion(input: {
  workspaceId: number;
  query: string;
  result: VocabSuggestResult;
  enrichSeq: { current: number };
}): Promise<{
  seq: number;
  candidate: VocabSuggestion;
  direction: VocabSuggestDirection;
  draft: VocabDraft | null;
  error: string | null;
}> {
  const direction = input.result.resolvedDirection ?? "en-to-target";
  const candidate = input.result.candidates[0];
  const seq = ++input.enrichSeq.current;

  try {
    const res = await enrichVocabSuggestion({
      workspaceId: input.workspaceId,
      inputText: input.query,
      selectedText: candidate.text,
      direction,
      pos: candidate.pos,
    });
    if (seq !== input.enrichSeq.current) {
      return { seq, candidate, direction, draft: null, error: null };
    }
    return { seq, candidate, direction, draft: res.draft, error: null };
  } catch {
    if (seq !== input.enrichSeq.current) {
      return { seq, candidate, direction, draft: null, error: null };
    }
    const surface = direction === "en-to-target" ? candidate.text : input.query;
    const gloss = direction === "en-to-target" ? input.query : candidate.text;
    return {
      seq,
      candidate,
      direction,
      draft: {
        surfaceForm: surface,
        lemma: surface,
        glossPrimary: gloss,
        glosses: [gloss],
        pos: candidate.pos,
        tags: [candidate.pos],
        cefr: null,
        frequencyRank: null,
        gender: null,
        conjugationClass: null,
        morphFeatures: null,
        ipa: null,
        notes: null,
      },
      error: "Metadata could not be prepared; you can still save this word",
    };
  }
}

export function swappedFieldValues(
  query: string,
  candidate: VocabSuggestion,
  direction: VocabSuggestDirection,
  draft: VocabDraft | null,
): { target: string; english: string } {
  if (draft) {
    return { target: draft.surfaceForm, english: draft.glossPrimary };
  }
  if (direction === "en-to-target") {
    return { target: candidate.text, english: query };
  }
  return { target: query, english: candidate.text };
}
