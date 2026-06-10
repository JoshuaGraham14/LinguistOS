"use client";

import { Loader2, Sparkles } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import {
  enrichVocabSuggestion,
  suggestVocab,
  type VocabDraft,
  type VocabSuggestion,
  type VocabSuggestDirection,
} from "@/lib/api";
import { useVocab } from "@/lib/storage";
import {
  applyAutoSwappedSuggestion,
  fieldSwapHint,
  swappedFieldValues,
  type VocabFieldSwapHint,
} from "@/lib/vocabSuggestAutomation";

type Props = {
  /** Called after a successful add. Useful for closing a modal. */
  onAdded?: (label: string) => void;
  /** Called when the user cancels (e.g. modal Cancel button). Hidden if not provided. */
  onCancel?: () => void;
  /** Auto-focus the surface form input on mount. */
  autoFocus?: boolean;
  /** Compact layout for sidebar use (smaller paddings, no helper paragraph). */
  variant?: "modal" | "compact";
};

export function QuickCaptureForm({
  onAdded,
  onCancel,
  autoFocus = false,
  variant = "modal",
}: Props) {
  const { addVocab, activeWorkspace } = useVocab();
  const [surfaceForm, setSurfaceForm] = useState("");
  const [translation, setTranslation] = useState("");
  const [activeSide, setActiveSide] = useState<"target" | "english">("target");
  const [suggestions, setSuggestions] = useState<VocabSuggestion[]>([]);
  const [suggesting, setSuggesting] = useState(false);
  const [enriching, setEnriching] = useState(false);
  const [draft, setDraft] = useState<VocabDraft | null>(null);
  const [selectionLocked, setSelectionLocked] = useState(false);
  const [swapHint, setSwapHint] = useState<VocabFieldSwapHint | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const suggestSeq = useRef(0);
  const enrichSeq = useRef(0);

  const direction: VocabSuggestDirection =
    activeSide === "english" ? "en-to-target" : "target-to-en";
  const activeText = activeSide === "english" ? translation : surfaceForm;

  useEffect(() => {
    if (autoFocus) {
      const id = window.setTimeout(() => inputRef.current?.focus(), 0);
      return () => window.clearTimeout(id);
    }
  }, [autoFocus]);

  useEffect(() => {
    if (selectionLocked || !activeWorkspace?.id) {
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
    setError(null);
    const timer = window.setTimeout(() => {
      void suggestVocab({
        workspaceId: activeWorkspace.id,
        inputText: query,
        direction,
      })
        .then(async (res) => {
          if (seq !== suggestSeq.current) return;
          if (res.fieldSwap && res.candidates.length > 0) {
            setSwapHint(fieldSwapHint(direction, activeWorkspace.language));
            setEnriching(true);
            const applied = await applyAutoSwappedSuggestion({
              workspaceId: activeWorkspace.id,
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
            setSurfaceForm(values.target);
            setTranslation(values.english);
            setActiveSide(applied.direction === "en-to-target" ? "english" : "target");
            setDraft(applied.draft);
            setSelectionLocked(true);
            setSuggestions(res.candidates.length > 1 ? res.candidates.slice(1) : []);
            setSuggesting(false);
            setEnriching(false);
            if (applied.error) setError(applied.error);
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
          setError("Could not load translation options");
        });
    }, 350);

    return () => window.clearTimeout(timer);
  }, [activeText, activeWorkspace?.id, direction, selectionLocked]);

  function resetAutomation(side: "target" | "english") {
    setActiveSide(side);
    setSelectionLocked(false);
    setDraft(null);
    setSwapHint(null);
    setError(null);
  }

  async function chooseSuggestion(candidate: VocabSuggestion) {
    if (!activeWorkspace?.id || enriching) return;
    const inputText = activeText.trim();
    if (!inputText) return;

    const seq = ++enrichSeq.current;
    setSelectionLocked(true);
    setSuggestions([]);
    setSuggesting(false);
    setEnriching(true);
    setError(null);

    if (direction === "en-to-target") {
      setSurfaceForm(candidate.text);
      setTranslation(inputText);
    } else {
      setSurfaceForm(inputText);
      setTranslation(candidate.text);
    }

    try {
      const res = await enrichVocabSuggestion({
        workspaceId: activeWorkspace.id,
        inputText,
        selectedText: candidate.text,
        direction,
        pos: candidate.pos,
      });
      if (seq !== enrichSeq.current) return;
      setDraft(res.draft);
      setSurfaceForm(res.draft.surfaceForm);
      setTranslation(res.draft.glossPrimary);
    } catch {
      if (seq !== enrichSeq.current) return;
      const surface = direction === "en-to-target" ? candidate.text : inputText;
      const gloss = direction === "en-to-target" ? inputText : candidate.text;
      setDraft({
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
      });
      setError("Metadata could not be prepared; you can still save this word");
    } finally {
      if (seq === enrichSeq.current) setEnriching(false);
    }
  }

  async function handleSubmit(event: React.FormEvent) {
    event.preventDefault();
    const surface = surfaceForm.trim();
    const gloss = translation.trim();
    if (!surface || !gloss || enriching) return;
    setSubmitting(true);
    setError(null);
    try {
      const item = await addVocab({
        surfaceForm: draft?.surfaceForm ?? surface,
        glossPrimary: draft?.glossPrimary ?? gloss,
        glosses: draft?.glosses ?? [gloss],
        lemma: draft?.lemma ?? surface,
        tags: draft?.tags ?? (draft?.pos ? [draft.pos] : []),
        pos: draft?.pos ?? null,
        cefr: draft?.cefr ?? null,
        frequencyRank: draft?.frequencyRank ?? null,
        gender: draft?.gender ?? null,
        conjugationClass: draft?.conjugationClass ?? null,
        morphFeatures: draft?.morphFeatures ?? null,
        ipa: draft?.ipa ?? null,
        notes: draft?.notes ?? null,
      });
      const label = item.surfaceForm ?? item.word ?? surface;
      setSurfaceForm("");
      setTranslation("");
      setDraft(null);
      setSelectionLocked(false);
      setSwapHint(null);
      setSubmitting(false);
      onAdded?.(label);
    } catch {
      setError("Could not add word");
      setSubmitting(false);
    }
  }

  const compact = variant === "compact";

  return (
    <form onSubmit={handleSubmit} className={compact ? "space-y-3" : "space-y-4"}>
      {!compact && (
        <p className="text-xs text-slate-500">
          Just the word as you saw or heard it. Translation, tags, and more
          can be filled later.
        </p>
      )}
      <label className="block">
        <span className="text-xs font-medium text-slate-700">
          {activeWorkspace?.language.toUpperCase() ?? "Word"}
        </span>
        <input
          ref={inputRef}
          value={surfaceForm}
          onFocus={() => setActiveSide("target")}
          onChange={(e) => {
            resetAutomation("target");
            setSurfaceForm(e.target.value);
          }}
          placeholder="e.g. hablamos"
          className={`mt-1 w-full rounded-xl border border-white/60 bg-white/60 backdrop-blur ${
            compact ? "px-3 py-2 text-sm" : "px-4 py-2.5"
          } focus:outline-none focus:ring-2 focus:ring-brand-400`}
        />
      </label>
      <label className="block">
        <span className="text-xs font-medium text-slate-700">
          English
        </span>
        <input
          value={translation}
          onFocus={() => setActiveSide("english")}
          onChange={(e) => {
            resetAutomation("english");
            setTranslation(e.target.value);
          }}
          placeholder="e.g. we speak"
          className={`mt-1 w-full rounded-xl border border-white/60 bg-white/60 backdrop-blur ${
            compact ? "px-3 py-2 text-sm" : "px-4 py-2.5"
          } focus:outline-none focus:ring-2 focus:ring-brand-400`}
        />
      </label>
      <div className="rounded-xl border border-white/60 bg-white/50 p-3 min-h-[68px]">
        <div className="flex items-center justify-between gap-3">
          <span className="inline-flex items-center gap-1.5 text-xs text-slate-500">
            <Sparkles className="h-3.5 w-3.5" strokeWidth={2} />
            {activeSide === "english"
              ? `English to ${activeWorkspace?.language.toUpperCase() ?? "word"}`
              : `${activeWorkspace?.language.toUpperCase() ?? "Word"} to English`}
          </span>
          {(suggesting || enriching) && (
            <Loader2 className="h-3.5 w-3.5 animate-spin text-slate-400" />
          )}
        </div>
        {suggestions.length > 0 ? (
          <div className="mt-2 flex flex-col gap-2">
            {suggestions.map((candidate) => (
              <button
                type="button"
                key={`${candidate.text}-${candidate.pos}`}
                onClick={() => {
                  void chooseSuggestion(candidate);
                }}
                className="rounded-xl border border-brand-200 bg-brand-50 px-3 py-2 text-left text-xs text-brand-700 hover:bg-brand-100 transition"
              >
                <span className="font-semibold">{candidate.text}</span>
                <span className="ml-1 uppercase tracking-wide text-brand-500">
                  {candidate.pos}
                </span>
                {candidate.context ? (
                  <span className="mt-0.5 block text-[11px] font-normal text-slate-500">
                    {candidate.context}
                  </span>
                ) : null}
              </button>
            ))}
          </div>
        ) : (
          <p className="mt-2 text-xs text-slate-500">
            {swapHint ? (
              <span className="text-brand-700">{swapHint.message}</span>
            ) : selectionLocked ? (
              "Translation selected."
            ) : activeText.trim().length < 2 ? (
              "Waiting for input."
            ) : suggesting || enriching ? (
              "Finding direct translations..."
            ) : (
              "No direct options yet."
            )}
          </p>
        )}
      </div>
      {error && <p className="text-xs text-rose-600">{error}</p>}
      <div className={`flex items-center ${compact ? "justify-end" : "justify-between"} gap-2 pt-1`}>
        {!compact && (
          <span className="inline-flex items-center gap-1.5 text-xs text-slate-500">
            <Sparkles className="h-3.5 w-3.5" strokeWidth={2} />
            Translation, lemma, and POS will be filled in for you.
          </span>
        )}
        <div className="flex gap-2">
          {onCancel && (
            <button
              type="button"
              onClick={onCancel}
              className="px-4 py-2 rounded-xl text-slate-600 hover:bg-slate-100 transition text-sm"
            >
              Cancel
            </button>
          )}
          <button
            type="submit"
            disabled={!surfaceForm.trim() || !translation.trim() || submitting || enriching}
            className={`${
              compact ? "px-3 py-1.5 text-sm" : "px-5 py-2"
            } rounded-xl bg-btn-purple text-white font-medium shadow-soft hover:brightness-110 disabled:opacity-50 disabled:cursor-not-allowed transition`}
          >
            {enriching ? "Preparing…" : submitting ? "Adding…" : "Add word"}
          </button>
        </div>
      </div>
    </form>
  );
}
