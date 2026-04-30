"use client";

import { Plus } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { Toast } from "./Toast";
import { useToast } from "@/lib/useToast";

interface ViewportPosition {
  /** CSS top in pixels (viewport coordinates, used with position:fixed). */
  top: number;
  left: number;
}

interface SelectionCaptureProps {
  /**
   * Element selector for the region(s) where text selection should trigger
   * the capture chip. Selecting text outside these regions is ignored.
   */
  containerRef: React.RefObject<HTMLElement | null>;
  /**
   * Caller-provided persistence hook. This keeps SelectionCapture stateless
   * with respect to workspace/vocab stores and avoids duplicate hook trees.
   */
  onAddWord: (surfaceForm: string) => Promise<string>;
  /** Optional callback invoked after a successful capture. */
  onCaptured?: (text: string) => void;
}

const MAX_SELECTION_LENGTH = 80;
const CHIP_GAP_PX = 36;

/**
 * Inline selection capture (LOS-402). When a user highlights a word inside
 * a watched container, a small "Add" chip appears near the selection and
 * stores the text as a new vocab item via the surface-form-only contract.
 * Multi-word selections are accepted; whitespace is collapsed.
 *
 * Positioning uses ``position: fixed`` against viewport coordinates, so
 * scrolling the page keeps the chip pinned to the visible selection.
 */
export function SelectionCapture({
  containerRef,
  onAddWord,
  onCaptured,
}: SelectionCaptureProps) {
  const [text, setText] = useState("");
  const [position, setPosition] = useState<ViewportPosition | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const { toast, showToast } = useToast();
  const buttonRef = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    function readSelection() {
      const selection = window.getSelection();
      if (!selection || selection.isCollapsed) {
        setPosition(null);
        return;
      }
      const range = selection.getRangeAt(0);
      const container = containerRef.current;
      if (!container) {
        setPosition(null);
        return;
      }
      const node = range.commonAncestorContainer;
      const owner = node instanceof Element ? node : node.parentElement;
      if (!owner || !container.contains(owner)) {
        setPosition(null);
        return;
      }
      const value = selection.toString().trim().replace(/\s+/g, " ");
      if (!value || value.length > MAX_SELECTION_LENGTH) {
        setPosition(null);
        return;
      }
      const rect = range.getBoundingClientRect();
      if (!rect || (rect.width === 0 && rect.height === 0)) {
        setPosition(null);
        return;
      }
      setText(value);
      // Viewport coordinates pair with position: fixed — scrolling keeps
      // the chip pinned to the visible selection.
      setPosition({
        top: rect.top - CHIP_GAP_PX,
        left: rect.left + rect.width / 2,
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

    document.addEventListener("mouseup", readSelection);
    document.addEventListener("keyup", readSelection);
    document.addEventListener("mousedown", handleMouseDown);
    return () => {
      document.removeEventListener("mouseup", readSelection);
      document.removeEventListener("keyup", readSelection);
      document.removeEventListener("mousedown", handleMouseDown);
    };
  }, [containerRef]);

  async function handleClick() {
    if (!text || submitting) return;
    setSubmitting(true);
    try {
      const saved = await onAddWord(text);
      showToast(`Added “${saved}”`);
      onCaptured?.(text);
      setPosition(null);
      window.getSelection()?.removeAllRanges();
    } catch {
      showToast("Could not add word");
    } finally {
      setSubmitting(false);
    }
  }

  const truncated =
    text.length > 24 ? `${text.slice(0, 24)}…` : text;

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
          {submitting ? "Adding…" : `Add “${truncated}”`}
        </button>
      )}
      <Toast message={toast} />
    </>
  );
}
