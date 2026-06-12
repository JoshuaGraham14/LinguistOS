import * as api from "./api";
import type { LanguageCode, VocabItem } from "./types";

const pollPromises = new Map<number, Promise<VocabItem>>();

/** Coalesce concurrent enrichment polls for the same vocab id. */
export function pollVocabEnrichedOnce(
  vocabId: number,
  language: LanguageCode,
): Promise<VocabItem> {
  const existing = pollPromises.get(vocabId);
  if (existing) return existing;

  const promise = api
    .pollVocabUntilEnriched(vocabId, language, {
      maxAttempts: 30,
      intervalMs: 1000,
    })
    .finally(() => {
      pollPromises.delete(vocabId);
    });
  pollPromises.set(vocabId, promise);
  return promise;
}
