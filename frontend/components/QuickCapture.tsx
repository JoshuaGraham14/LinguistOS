"use client";

import { Plus, Sparkles } from "lucide-react";
import { useCallback, useEffect, useRef, useState } from "react";
import { Modal } from "./Modal";
import { useGlobalShortcut } from "@/lib/useGlobalShortcut";
import { useVocab } from "@/lib/storage";

/**
 * Global low-friction word capture (LOS-401).
 *
 * Single required field (surface form) + optional meaning. Triggered from
 * any page via Cmd/Ctrl+K or by exposing setOpen via context (future).
 * Only the surface form is required to save; everything else is filled
 * later by the enrichment pipeline (LOS-106).
 */
export function QuickCapture() {
  const { addVocab, activeWorkspace } = useVocab();
  const [open, setOpen] = useState(false);
  const [surfaceForm, setSurfaceForm] = useState("");
  const [translation, setTranslation] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [toast, setToast] = useState<string | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  const openCapture = useCallback(() => setOpen(true), []);
  useGlobalShortcut({ key: "k", meta: true, ctrl: true }, openCapture);

  useEffect(() => {
    if (!open) return;
    const id = window.setTimeout(() => inputRef.current?.focus(), 0);
    return () => window.clearTimeout(id);
  }, [open]);

  useEffect(() => {
    if (!toast) return;
    const id = window.setTimeout(() => setToast(null), 2200);
    return () => window.clearTimeout(id);
  }, [toast]);

  function reset() {
    setSurfaceForm("");
    setTranslation("");
    setSubmitting(false);
  }

  function handleClose() {
    setOpen(false);
    reset();
  }

  async function handleSubmit(event: React.FormEvent) {
    event.preventDefault();
    const surface = surfaceForm.trim();
    if (!surface) return;
    setSubmitting(true);
    try {
      const item = await addVocab({
        surfaceForm: surface,
        glossPrimary: translation.trim() || undefined,
      });
      setToast(`Added "${item.surfaceForm ?? item.word}"`);
      handleClose();
    } catch {
      setToast("Could not add word");
      setSubmitting(false);
    }
  }

  return (
    <>
      <button
        type="button"
        onClick={openCapture}
        className="fixed bottom-6 right-6 z-40 inline-flex items-center gap-2 rounded-full bg-btn-purple text-white px-5 py-3 shadow-card hover:brightness-110 transition"
        aria-label="Quick capture a word"
      >
        <Plus className="h-4 w-4" strokeWidth={2.5} />
        Quick add
        <kbd className="ml-1 px-1.5 py-0.5 rounded bg-white/20 text-[10px]">
          {typeof navigator !== "undefined" && navigator.platform.includes("Mac")
            ? "⌘K"
            : "Ctrl+K"}
        </kbd>
      </button>

      <Modal open={open} onClose={handleClose} title="Quick add a word">
        <form onSubmit={handleSubmit} className="space-y-4">
          <p className="text-xs text-slate-500">
            Just the word as you saw or heard it. Translation, tags, and more
            can be filled later.
          </p>
          <label className="block">
            <span className="text-sm font-medium text-slate-700">
              {activeWorkspace?.language.toUpperCase() ?? "Word"}
            </span>
            <input
              ref={inputRef}
              value={surfaceForm}
              onChange={(e) => setSurfaceForm(e.target.value)}
              placeholder="e.g. hablamos"
              className="mt-1 w-full rounded-xl border border-slate-200 px-4 py-2.5 focus:outline-none focus:ring-2 focus:ring-brand-400"
            />
          </label>
          <label className="block">
            <span className="text-sm font-medium text-slate-700">
              Meaning <span className="text-slate-400">(optional)</span>
            </span>
            <input
              value={translation}
              onChange={(e) => setTranslation(e.target.value)}
              placeholder="e.g. we speak"
              className="mt-1 w-full rounded-xl border border-slate-200 px-4 py-2.5 focus:outline-none focus:ring-2 focus:ring-brand-400"
            />
          </label>
          <div className="flex items-center justify-between gap-2 pt-2">
            <span className="inline-flex items-center gap-1.5 text-xs text-slate-500">
              <Sparkles className="h-3.5 w-3.5" strokeWidth={2} />
              Translation, lemma, and POS will be filled in for you.
            </span>
            <div className="flex gap-2">
              <button
                type="button"
                onClick={handleClose}
                className="px-4 py-2 rounded-xl text-slate-600 hover:bg-slate-100 transition"
              >
                Cancel
              </button>
              <button
                type="submit"
                disabled={!surfaceForm.trim() || submitting}
                className="px-5 py-2 rounded-xl bg-btn-purple text-white font-medium shadow-soft hover:brightness-110 disabled:opacity-50 disabled:cursor-not-allowed transition"
              >
                {submitting ? "Adding…" : "Add word"}
              </button>
            </div>
          </div>
        </form>
      </Modal>

      {toast && (
        <div
          className="fixed bottom-24 right-6 z-50 rounded-xl bg-slate-900 text-white px-4 py-2 text-sm shadow-card"
          role="status"
        >
          {toast}
        </div>
      )}
    </>
  );
}
