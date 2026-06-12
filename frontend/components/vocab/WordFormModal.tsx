"use client";

import { Loader2, Sparkles } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { Modal } from "@/components/Modal";
import {
  enrichVocabSuggestion,
  suggestVocab,
  type VocabDraft,
  type VocabSuggestion,
  type VocabSuggestDirection,
} from "@/lib/api";
import { cn } from "@/lib/cn";
import type { WordFormInput } from "@/lib/vocab-csv";
import {
  applyAutoSwappedSuggestion,
  fieldSwapHint,
  swappedFieldValues,
  type VocabFieldSwapHint,
} from "@/lib/vocabSuggestAutomation";
import type { VocabItem, VocabTag } from "@/lib/types";

const TAG_OPTIONS: VocabTag[] = [
  "noun",
  "verb",
  "adjective",
  "adverb",
  "preposition",
  "other",
];

export function WordFormModal({
  open,
  onClose,
  onSubmit,
  title,
  submitLabel,
  sourceLanguageLabel,
  workspaceId,
  initial,
}: {
  open: boolean;
  onClose: () => void;
  onSubmit: (input: WordFormInput) => void;
  title: string;
  submitLabel: string;
  sourceLanguageLabel: string;
  workspaceId: number | null;
  initial?: VocabItem | null;
}) {
  const [word, setWord] = useState(initial?.word ?? "");
  const [translation, setTranslation] = useState(initial?.translation ?? "");
  const [tags, setTags] = useState<VocabTag[]>(initial?.tags ?? []);
  const [activeSide, setActiveSide] = useState<"target" | "english">("target");
  const [suggestions, setSuggestions] = useState<VocabSuggestion[]>([]);
  const [suggesting, setSuggesting] = useState(false);
  const [enriching, setEnriching] = useState(false);
  const [autoError, setAutoError] = useState<string | null>(null);
  const [draft, setDraft] = useState<VocabDraft | null>(null);
  const [selectionLocked, setSelectionLocked] = useState(false);
  const [swapHint, setSwapHint] = useState<VocabFieldSwapHint | null>(null);
  const suggestSeq = useRef(0);
  const enrichSeq = useRef(0);
  const isEditing = Boolean(initial);
  const targetLanguageCode = sourceLanguageLabel.toLowerCase();

  useEffect(() => {
    if (!open) return;
    setWord(initial?.word ?? "");
    setTranslation(initial?.translation ?? "");
    setTags(initial?.tags ?? []);
    setActiveSide("target");
    setSuggestions([]);
    setSuggesting(false);
    setEnriching(false);
    setAutoError(null);
    setDraft(null);
    setSelectionLocked(false);
    setSwapHint(null);
  }, [open, initial?.id, initial?.word, initial?.translation, initial?.tags]);

  const direction: VocabSuggestDirection =
    activeSide === "english" ? "en-to-target" : "target-to-en";
  const activeText = activeSide === "english" ? translation : word;

  useEffect(() => {
    if (!open || isEditing || selectionLocked || !workspaceId) {
      setSuggestions([]);
      setSuggesting(false);
      return;
    }
    const query = activeText.trim();
    if (query.length < 2) {
      setSuggestions([]);
      setSuggesting(false);
      return;
    }

    const seq = ++suggestSeq.current;
    setSuggesting(true);
    setAutoError(null);
    const timer = window.setTimeout(() => {
      void suggestVocab({
        workspaceId,
        inputText: query,
        direction,
      })
        .then(async (res) => {
          if (seq !== suggestSeq.current) return;
          if (res.fieldSwap && res.candidates.length > 0) {
            setSwapHint(fieldSwapHint(direction, targetLanguageCode));
            setEnriching(true);
            const applied = await applyAutoSwappedSuggestion({
              workspaceId,
              query,
              result: res,
              enrichSeq,
            });
            if (seq !== suggestSeq.current) return;
            const values = swappedFieldValues(
              query,
              applied.candidate,
              applied.direction,
              applied.draft,
            );
            setWord(values.target);
            setTranslation(values.english);
            setActiveSide(applied.direction === "en-to-target" ? "english" : "target");
            setDraft(applied.draft);
            if (applied.draft?.tags.length) {
              setTags(applied.draft.tags);
            } else {
              setTags([applied.candidate.pos]);
            }
            setSelectionLocked(true);
            setSuggestions(res.candidates.length > 1 ? res.candidates.slice(1) : []);
            setSuggesting(false);
            setEnriching(false);
            if (applied.error) setAutoError(applied.error);
            return;
          }
          setSwapHint(null);
          setSuggestions(res.candidates);
          setSuggesting(false);
        })
        .catch(() => {
          if (seq !== suggestSeq.current) return;
          setSuggestions([]);
          setSuggesting(false);
          setSwapHint(null);
          setAutoError("Could not load translation options");
        });
    }, 350);

    return () => window.clearTimeout(timer);
  }, [activeText, direction, isEditing, open, selectionLocked, workspaceId]);

  function resetAutomation(side: "target" | "english") {
    setActiveSide(side);
    setSelectionLocked(false);
    setDraft(null);
    setSwapHint(null);
    setAutoError(null);
  }

  function toggleTag(tag: VocabTag) {
    setTags((t) =>
      t.includes(tag) ? t.filter((x) => x !== tag) : [...t, tag],
    );
  }

  async function chooseSuggestion(candidate: VocabSuggestion) {
    if (!workspaceId || enriching) return;
    const inputText = activeText.trim();
    if (!inputText) return;

    const seq = ++enrichSeq.current;
    setSelectionLocked(true);
    setSuggestions([]);
    setSuggesting(false);
    setEnriching(true);
    setAutoError(null);

    if (direction === "en-to-target") {
      setWord(candidate.text);
      setTranslation(inputText);
    } else {
      setWord(inputText);
      setTranslation(candidate.text);
    }
    setTags([candidate.pos]);

    try {
      const res = await enrichVocabSuggestion({
        workspaceId,
        inputText,
        selectedText: candidate.text,
        direction,
        pos: candidate.pos,
      });
      if (seq !== enrichSeq.current) return;
      setDraft(res.draft);
      setWord(res.draft.surfaceForm);
      setTranslation(res.draft.glossPrimary);
      setTags(res.draft.tags.length ? res.draft.tags : [res.draft.pos]);
    } catch {
      if (seq !== enrichSeq.current) return;
      setDraft({
        surfaceForm: direction === "en-to-target" ? candidate.text : inputText,
        lemma: direction === "en-to-target" ? candidate.text : inputText,
        glossPrimary: direction === "en-to-target" ? inputText : candidate.text,
        glosses: [direction === "en-to-target" ? inputText : candidate.text],
        pos: candidate.pos,
        tags: [candidate.pos],
        cefr: null,
        frequencyRank: null,
        gender: null,
        conjugationClass: null,
        morphFeatures: null,
        ipa: null,
        notes: null,
      });
      setAutoError("Metadata could not be prepared; you can still save this word");
    } finally {
      if (seq === enrichSeq.current) setEnriching(false);
    }
  }

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    const surface = word.trim();
    const gloss = translation.trim();
    if (!surface || !gloss || enriching) return;
    onSubmit({
      word: surface,
      translation: gloss,
      tags,
      surfaceForm: draft?.surfaceForm ?? surface,
      glossPrimary: draft?.glossPrimary ?? gloss,
      glosses: draft?.glosses ?? [gloss],
      lemma: draft?.lemma ?? surface,
      pos: draft?.pos ?? tags[0] ?? null,
      cefr: draft?.cefr ?? null,
      frequencyRank: draft?.frequencyRank ?? null,
      gender: draft?.gender ?? null,
      conjugationClass: draft?.conjugationClass ?? null,
      morphFeatures: draft?.morphFeatures ?? null,
      ipa: draft?.ipa ?? null,
      notes: draft?.notes ?? null,
    });
    onClose();
  }

  const activeInputClass =
    "ring-2 ring-brand-300 border-brand-200 bg-white";

  return (
    <Modal open={open} onClose={onClose} title={title}>
      <form onSubmit={handleSubmit} className="space-y-4">
        <label className="block">
          <span className="text-sm font-medium text-slate-700">{sourceLanguageLabel}</span>
          <input
            value={word}
            onFocus={() => setActiveSide("target")}
            onChange={(e) => {
              resetAutomation("target");
              setWord(e.target.value);
            }}
            placeholder="e.g. correr"
            autoFocus
            className={cn(
              "mt-1 w-full rounded-xl border border-slate-200 px-4 py-2.5 focus:outline-none focus:ring-2 focus:ring-brand-400",
              !isEditing && activeSide === "target" && activeInputClass,
            )}
          />
        </label>
        <label className="block">
          <span className="text-sm font-medium text-slate-700">English</span>
          <input
            value={translation}
            onFocus={() => setActiveSide("english")}
            onChange={(e) => {
              resetAutomation("english");
              setTranslation(e.target.value);
            }}
            placeholder="e.g. to run"
            className={cn(
              "mt-1 w-full rounded-xl border border-slate-200 px-4 py-2.5 focus:outline-none focus:ring-2 focus:ring-brand-400",
              !isEditing && activeSide === "english" && activeInputClass,
            )}
          />
        </label>

        {!isEditing && (
          <div className="rounded-xl border border-slate-200 bg-white/70 p-3 min-h-[76px]">
            <div className="flex items-center justify-between gap-3">
              <span className="inline-flex items-center gap-1.5 text-xs font-medium text-slate-600">
                <Sparkles className="h-3.5 w-3.5 text-brand-500" strokeWidth={2.5} />
                {activeSide === "english"
                  ? `English to ${sourceLanguageLabel}`
                  : `${sourceLanguageLabel} to English`}
              </span>
              {(suggesting || enriching) && (
                <span className="inline-flex items-center gap-1.5 text-xs text-slate-500">
                  <Loader2 className="h-3.5 w-3.5 animate-spin" />
                  {enriching ? "Preparing word" : "Finding options"}
                </span>
              )}
            </div>

            {suggestions.length > 0 ? (
              <div className="mt-3 flex flex-col gap-2">
                {suggestions.map((candidate) => (
                  <button
                    type="button"
                    key={`${candidate.text}-${candidate.pos}`}
                    onClick={() => {
                      void chooseSuggestion(candidate);
                    }}
                    className="rounded-xl border border-brand-200 bg-brand-50 px-3 py-2 text-left text-sm text-brand-700 hover:bg-brand-100 transition"
                  >
                    <span className="font-semibold">{candidate.text}</span>
                    <span className="ml-1.5 text-xs uppercase tracking-wide text-brand-500">
                      {candidate.pos}
                    </span>
                    {candidate.context ? (
                      <span className="mt-0.5 block text-xs font-normal text-slate-500">
                        {candidate.context}
                      </span>
                    ) : null}
                  </button>
                ))}
              </div>
            ) : (
              <p className="mt-3 text-xs text-slate-500">
                {swapHint ? (
                  <span className="text-brand-700">{swapHint.message}</span>
                ) : activeText.trim().length < 2 ? (
                  "Type either side to look up direct translations."
                ) : selectionLocked ? (
                  "Translation selected. Metadata is ready to save."
                ) : suggesting || enriching ? (
                  "Looking for direct translations..."
                ) : (
                  "No direct options yet. You can still enter both sides manually."
                )}
              </p>
            )}
            {autoError && <p className="mt-2 text-xs text-rose-600">{autoError}</p>}
          </div>
        )}

        <div>
          <span className="text-sm font-medium text-slate-700">Tags</span>
          <div className="mt-2 flex flex-wrap gap-2">
            {TAG_OPTIONS.map((tag) => (
              <button
                type="button"
                key={tag}
                onClick={() => toggleTag(tag)}
                className={cn(
                  "px-3 py-1.5 rounded-full text-sm border transition capitalize",
                  tags.includes(tag)
                    ? "bg-brand-100 border-brand-300 text-brand-700"
                    : "bg-white border-slate-200 text-slate-600 hover:bg-slate-50",
                )}
              >
                {tag}
              </button>
            ))}
          </div>
        </div>
        <div className="flex justify-end gap-2 pt-2">
          <button
            type="button"
            onClick={onClose}
            className="px-4 py-2 rounded-xl text-slate-600 hover:bg-slate-100 transition"
          >
            Cancel
          </button>
          <button
            type="submit"
            disabled={!word.trim() || !translation.trim() || enriching}
            className="px-5 py-2 rounded-xl bg-btn-purple text-white font-medium shadow-soft hover:brightness-110 disabled:opacity-50 disabled:cursor-not-allowed transition"
          >
            {enriching ? "Preparing…" : submitLabel}
          </button>
        </div>
      </form>
    </Modal>
  );
}
