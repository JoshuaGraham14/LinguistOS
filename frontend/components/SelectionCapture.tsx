"use client";

import { Plus } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { useVocab } from "@/lib/storage";

interface Position {
  top: number;
  left: number;
}

interface SelectionCaptureProps {
  /**
   * Element selector for the region(s) where text selection should trigger
   * the capture chip. Selecting text outside these regions is ignored.
   */
  containerRef: React.RefObject<HTMLElement | null>;
  /** Optional callback invoked after a successful capture. */
  onCaptured?: (text: string) => void;
}

/**
 * Inline selection capture (LOS-402). When a user highlights a word inside
 * a watched container, a small "Add" chip appears near the selection and
 * stores the text as a new vocab item via QuickCapture's surface-only
 * contract. Multi-word selections are accepted; whitespace is collapsed.
 */
export function SelectionCapture({ containerRef, onCaptured }: SelectionCaptureProps) {
  const { addVocab, activeWorkspace } = useVocab();
  const [text, setText] = useState("");
  const [position, setPosition] = useState<Position | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [toast, setToast] = useState<string | null>(null);
  const buttonRef = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    function handleSelection() {
      const selection = window.getSelection();
      if (!selection || selection.isCollapsed) {
        setPosition(null);
        return;
      }
      const range = selection.getRangeAt(0);
      const node = range.commonAncestorContainer;
      const container = containerRef.current;
      if (!container) {
        setPosition(null);
        return;
      }
      const owner =
        node instanceof Element ? node : node.parentElement;
      if (!owner || !container.contains(owner)) {
        setPosition(null);
        return;
      }
      const value = selection.toString().trim().replace(/\s+/g, " ");
      if (!value || value.length > 80) {
        setPosition(null);
        return;
      }
      const rect = range.getBoundingClientRect();
      if (!rect || (rect.width === 0 && rect.height === 0)) {
        setPosition(null);
        return;
      }
      setText(value);
      setPosition({
        top: rect.top + window.scrollY - 36,
        left: rect.left + window.scrollX + rect.width / 2,
      });
    }

    function handleMouseDown(event: MouseEvent) {
      // Clicking the button itself shouldn't dismiss the chip mid-press.
      if (
        buttonRef.current &&
        buttonRef.current.contains(event.target as Node)
      ) {
        return;
      }
      setPosition(null);
    }

    document.addEventListener("mouseup", handleSelection);
    document.addEventListener("keyup", handleSelection);
    document.addEventListener("mousedown", handleMouseDown);
    return () => {
      document.removeEventListener("mouseup", handleSelection);
      document.removeEventListener("keyup", handleSelection);
      document.removeEventListener("mousedown", handleMouseDown);
    };
  }, [containerRef]);

  useEffect(() => {
    if (!toast) return;
    const id = window.setTimeout(() => setToast(null), 2000);
    return () => window.clearTimeout(id);
  }, [toast]);

  async function handleClick() {
    if (!text || submitting || !activeWorkspace) return;
    setSubmitting(true);
    try {
      const item = await addVocab({ surfaceForm: text });
      setToast(`Added "${item.surfaceForm ?? item.word}"`);
      onCaptured?.(text);
      setPosition(null);
      window.getSelection()?.removeAllRanges();
    } catch {
      setToast("Could not add word");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <>
      {position && (
        <button
          ref={buttonRef}
          type="button"
          onMouseDown={(e) => e.preventDefault()}
          onClick={handleClick}
          style={{ top: position.top, left: position.left }}
          className="fixed z-50 -translate-x-1/2 inline-flex items-center gap-1 rounded-full bg-slate-900 text-white px-3 py-1 text-xs font-medium shadow-card hover:bg-slate-800 transition"
        >
          <Plus className="h-3 w-3" strokeWidth={2.5} />
          {submitting ? "Adding…" : `Add "${text.length > 24 ? `${text.slice(0, 24)}…` : text}"`}
        </button>
      )}
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
