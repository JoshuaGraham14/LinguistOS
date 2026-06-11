"use client";

import { Check } from "lucide-react";
import type { LucideIcon } from "lucide-react";
import { useEffect, useLayoutEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { cn } from "@/lib/cn";

export function ContextMenu({
  open,
  x,
  y,
  onClose,
  children,
  minWidth = 200,
}: {
  open: boolean;
  x: number;
  y: number;
  onClose: () => void;
  children: React.ReactNode;
  minWidth?: number;
}) {
  const menuRef = useRef<HTMLDivElement>(null);
  const [pos, setPos] = useState({ top: y, left: x });

  useLayoutEffect(() => {
    if (!open) return;
    const el = menuRef.current;
    if (!el) {
      setPos({ top: y, left: x });
      return;
    }
    const rect = el.getBoundingClientRect();
    setPos({
      left: Math.max(12, Math.min(x, window.innerWidth - rect.width - 12)),
      top: Math.max(12, Math.min(y, window.innerHeight - rect.height - 12)),
    });
  }, [open, x, y, children]);

  useEffect(() => {
    if (!open) return;
    function onKey(e: KeyboardEvent) {
      if (e.key === "Escape") onClose();
    }
    function onClick(e: MouseEvent) {
      if (menuRef.current?.contains(e.target as Node)) return;
      onClose();
    }
    document.addEventListener("keydown", onKey);
    document.addEventListener("mousedown", onClick);
    return () => {
      document.removeEventListener("keydown", onKey);
      document.removeEventListener("mousedown", onClick);
    };
  }, [open, onClose]);

  if (!open || typeof document === "undefined") return null;

  return createPortal(
    <div
      ref={menuRef}
      role="menu"
      className="fixed z-[360] rounded-xl border border-slate-200 bg-white shadow-lg py-1.5"
      style={{ top: pos.top, left: pos.left, minWidth }}
    >
      {children}
    </div>,
    document.body,
  );
}

export function ContextMenuItem({
  icon: Icon,
  onClick,
  disabled,
  destructive,
  active,
  title,
  children,
}: {
  icon?: LucideIcon;
  onClick?: () => void;
  disabled?: boolean;
  destructive?: boolean;
  active?: boolean;
  title?: string;
  children: React.ReactNode;
}) {
  return (
    <button
      type="button"
      role="menuitem"
      disabled={disabled}
      title={title}
      onClick={() => {
        if (disabled) return;
        onClick?.();
      }}
      className={cn(
        "w-full flex items-center gap-2.5 px-3 py-2 text-sm transition disabled:opacity-40 disabled:cursor-not-allowed",
        destructive
          ? "text-rose-600 hover:bg-rose-50"
          : "text-slate-700 hover:bg-slate-50",
      )}
    >
      {Icon && (
        <Icon
          className={cn(
            "h-4 w-4 shrink-0",
            destructive ? "text-rose-500" : "text-slate-500",
          )}
          strokeWidth={2}
        />
      )}
      <span className="flex-1 text-left">{children}</span>
      {active && <Check className="h-4 w-4 shrink-0 text-brand-600" />}
    </button>
  );
}

export function ContextMenuLink({
  href,
  icon: Icon,
  onClick,
  children,
}: {
  href: string;
  icon?: LucideIcon;
  onClick?: () => void;
  children: React.ReactNode;
}) {
  return (
    <a
      href={href}
      role="menuitem"
      onClick={onClick}
      className="flex items-center gap-2.5 px-3 py-2 text-sm text-slate-700 hover:bg-slate-50 transition"
    >
      {Icon && (
        <Icon className="h-4 w-4 shrink-0 text-slate-500" strokeWidth={2} />
      )}
      <span className="flex-1">{children}</span>
    </a>
  );
}

export function ContextMenuSeparator() {
  return <div className="my-1 border-t border-slate-100" role="separator" />;
}
