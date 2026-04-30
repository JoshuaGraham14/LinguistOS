"use client";

import { X } from "lucide-react";
import { useEffect } from "react";
import { createPortal } from "react-dom";

export function Modal({
  open,
  onClose,
  title,
  children,
}: {
  open: boolean;
  onClose: () => void;
  title: string;
  children: React.ReactNode;
}) {
  useEffect(() => {
    if (!open) return;
    function handleKey(e: KeyboardEvent) {
      if (e.key === "Escape") onClose();
    }
    document.addEventListener("keydown", handleKey);
    return () => document.removeEventListener("keydown", handleKey);
  }, [open, onClose]);

  if (!open) return null;

  const modal = (
    <div
      className="fixed inset-0 z-[420] flex items-center justify-center bg-slate-900/30 backdrop-blur-sm p-4"
      onClick={onClose}
    >
      <div
        className="glass-card-strong glass-gloss w-full max-w-md rounded-2xl p-6"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="relative flex items-center justify-between mb-4">
          <h2 className="text-xl font-bold text-slate-900">{title}</h2>
          <button
            type="button"
            onClick={onClose}
            className="p-2 rounded-lg text-slate-400 hover:bg-white/60 transition"
            aria-label="Close"
          >
            <X className="h-4 w-4" strokeWidth={2.5} />
          </button>
        </div>
        <div className="relative">{children}</div>
      </div>
    </div>
  );
  if (typeof document === "undefined") return null;
  return createPortal(modal, document.body);
}
