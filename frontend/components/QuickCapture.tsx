"use client";

import { Plus } from "lucide-react";
import { useCallback, useState } from "react";
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
  const { toast, showToast } = useToast();

  const openCapture = useCallback(() => setOpen(true), []);
  useGlobalShortcut({ key: "k", meta: true, ctrl: true }, openCapture);

  const handleClose = () => setOpen(false);

  return (
    <>
      <button
        type="button"
        onClick={openCapture}
        className="lg:hidden fixed bottom-6 right-6 z-40 inline-flex items-center gap-2 rounded-full bg-btn-purple text-white px-5 py-3 shadow-glass hover:brightness-110 transition"
        aria-label="Quick capture a word"
      >
        <Plus className="h-4 w-4" strokeWidth={2.5} />
        Quick add
        <kbd className="ml-1 px-1.5 py-0.5 rounded bg-white/20 text-[10px]">
          {shortcutLabel("k")}
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
