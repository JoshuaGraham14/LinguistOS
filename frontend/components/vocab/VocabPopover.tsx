"use client";

import { useEffect, useLayoutEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";

export function VocabPopover({
  open,
  onClose,
  anchorRef,
  title,
  children,
  width = 340,
}: {
  open: boolean;
  onClose: () => void;
  anchorRef: React.RefObject<HTMLElement | null>;
  title: string;
  children: React.ReactNode;
  width?: number;
}) {
  const panelRef = useRef<HTMLDivElement>(null);
  const [pos, setPos] = useState({ top: 0, left: 0 });

  useLayoutEffect(() => {
    if (!open || !anchorRef.current) return;
    const rect = anchorRef.current.getBoundingClientRect();
    const maxLeft = window.innerWidth - width - 12;
    setPos({
      top: rect.bottom + 8,
      left: Math.max(12, Math.min(rect.right - width, maxLeft)),
    });
  }, [open, anchorRef, width]);

  useEffect(() => {
    if (!open) return;
    function onKey(e: KeyboardEvent) {
      if (e.key === "Escape") onClose();
    }
    function onClick(e: MouseEvent) {
      const t = e.target as Node;
      if (panelRef.current?.contains(t)) return;
      if (anchorRef.current?.contains(t)) return;
      onClose();
    }
    document.addEventListener("keydown", onKey);
    document.addEventListener("mousedown", onClick);
    return () => {
      document.removeEventListener("keydown", onKey);
      document.removeEventListener("mousedown", onClick);
    };
  }, [open, onClose, anchorRef]);

  if (!open || typeof document === "undefined") return null;

  return createPortal(
    <div
      ref={panelRef}
      className="fixed z-[350] glass-card-strong rounded-xl border border-slate-200 shadow-lg overflow-hidden"
      style={{ top: pos.top, left: pos.left, width }}
    >
      <div className="px-4 py-3 border-b border-slate-100 bg-slate-50/80">
        <h3 className="text-sm font-semibold text-slate-900">{title}</h3>
      </div>
      <div className="p-4 max-h-[min(70vh,480px)] overflow-y-auto">{children}</div>
    </div>,
    document.body,
  );
}
