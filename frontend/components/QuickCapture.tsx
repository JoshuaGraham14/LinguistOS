"use client";

import { Plus } from "lucide-react";
import { useCallback, useEffect, useState } from "react";
import { Modal } from "./Modal";
import { QuickCaptureForm } from "./QuickCaptureForm";
import { Toast } from "./Toast";
import { shortcutLabel } from "@/lib/platform";
import { useGlobalShortcut } from "@/lib/useGlobalShortcut";
import { useToast } from "@/lib/useToast";

/**
 * Global low-friction word capture (LOS-401). Floating button + Cmd/Ctrl+K
 * shortcut. The actual form lives in QuickCaptureForm and is reused by the
 * right-sidebar inline panel.
 */
export function QuickCapture() {
  const [open, setOpen] = useState(false);
  // Render a placeholder label on the server and the first client paint, then
  // resolve to the platform-specific shortcut after mount. Without this two-
  // step approach React would hydrate-mismatch since `navigator` is unavailable
  // on the server.
  const [shortcut, setShortcut] = useState("K");
  const { toast, showToast } = useToast();

  const openCapture = useCallback(() => setOpen(true), []);
  useGlobalShortcut({ key: "k", meta: true, ctrl: true }, openCapture);

  useEffect(() => {
    setShortcut(shortcutLabel("k"));
  }, []);

  const handleClose = () => setOpen(false);

  return (
    <>
      <button
        type="button"
        onClick={openCapture}
        className="fixed bottom-6 right-6 z-40 inline-flex items-center gap-2 rounded-full bg-btn-rainbow text-slate-800 px-5 py-3 shadow-glass-lg border border-white/60 hover:brightness-105 hover:-translate-y-0.5 transition glass-gloss"
        aria-label="Quick capture a word"
      >
        <Plus className="h-4 w-4 relative" strokeWidth={2.5} />
        <span className="relative font-medium">Quick add</span>
        <kbd className="relative ml-1 px-1.5 py-0.5 rounded bg-white/60 border border-white/60 text-[10px] font-medium text-slate-700">
          {shortcut}
        </kbd>
      </button>

      <Modal open={open} onClose={handleClose} title="Quick add a word">
        <QuickCaptureForm
          autoFocus
          onCancel={handleClose}
          onAdded={(label) => {
            showToast(`Added "${label}"`);
            handleClose();
          }}
        />
      </Modal>

      <Toast message={toast} />
    </>
  );
}
