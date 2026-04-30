"use client";

import { Modal } from "./Modal";
import { QuickCaptureForm } from "./QuickCaptureForm";
import { useQuickCapture } from "./QuickCaptureContext";
import { Toast } from "./Toast";
import { useGlobalShortcut } from "@/lib/useGlobalShortcut";
import { useToast } from "@/lib/useToast";

/**
 * Global low-friction word capture (LOS-401). Floating button + Cmd/Ctrl+K
 * shortcut. The actual form lives in QuickCaptureForm and is reused by the
 * right-sidebar inline panel.
 */
export function QuickCapture() {
  const { open, openCapture, closeCapture } = useQuickCapture();
  const { toast, showToast } = useToast();

  useGlobalShortcut({ key: "k", meta: true, ctrl: true }, openCapture);

  const handleClose = closeCapture;

  return (
    <>
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
