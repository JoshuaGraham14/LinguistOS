"use client";

import { Sparkles } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { useVocab } from "@/lib/storage";

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
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (autoFocus) {
      const id = window.setTimeout(() => inputRef.current?.focus(), 0);
      return () => window.clearTimeout(id);
    }
  }, [autoFocus]);

  async function handleSubmit(event: React.FormEvent) {
    event.preventDefault();
    const surface = surfaceForm.trim();
    if (!surface) return;
    setSubmitting(true);
    setError(null);
    try {
      const item = await addVocab({
        surfaceForm: surface,
        glossPrimary: translation.trim() || undefined,
      });
      const label = item.surfaceForm ?? item.word ?? surface;
      setSurfaceForm("");
      setTranslation("");
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
          onChange={(e) => setSurfaceForm(e.target.value)}
          placeholder="e.g. hablamos"
          className={`mt-1 w-full rounded-xl border border-white/60 bg-white/60 backdrop-blur ${
            compact ? "px-3 py-2 text-sm" : "px-4 py-2.5"
          } focus:outline-none focus:ring-2 focus:ring-brand-400`}
        />
      </label>
      <label className="block">
        <span className="text-xs font-medium text-slate-700">
          Meaning <span className="text-slate-400">(optional)</span>
        </span>
        <input
          value={translation}
          onChange={(e) => setTranslation(e.target.value)}
          placeholder="e.g. we speak"
          className={`mt-1 w-full rounded-xl border border-white/60 bg-white/60 backdrop-blur ${
            compact ? "px-3 py-2 text-sm" : "px-4 py-2.5"
          } focus:outline-none focus:ring-2 focus:ring-brand-400`}
        />
      </label>
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
            disabled={!surfaceForm.trim() || submitting}
            className={`${
              compact ? "px-3 py-1.5 text-sm" : "px-5 py-2"
            } rounded-xl bg-btn-purple text-white font-medium shadow-soft hover:brightness-110 disabled:opacity-50 disabled:cursor-not-allowed transition`}
          >
            {submitting ? "Adding…" : "Add word"}
          </button>
        </div>
      </div>
    </form>
  );
}
