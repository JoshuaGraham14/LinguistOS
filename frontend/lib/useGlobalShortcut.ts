"use client";

import { useEffect } from "react";

export interface GlobalShortcut {
  /** Lowercase key character, e.g. "k". */
  key: string;
  meta?: boolean;
  ctrl?: boolean;
  shift?: boolean;
  alt?: boolean;
}

/**
 * Subscribe to a single global keyboard shortcut. Ignores keystrokes when
 * focus is inside an input/textarea/contenteditable so the shortcut never
 * steals user typing.
 */
export function useGlobalShortcut(
  shortcut: GlobalShortcut,
  handler: (event: KeyboardEvent) => void,
  enabled = true,
): void {
  useEffect(() => {
    if (!enabled || typeof window === "undefined") return;

    function isEditableTarget(target: EventTarget | null) {
      if (!(target instanceof HTMLElement)) return false;
      const tag = target.tagName;
      if (tag === "INPUT" || tag === "TEXTAREA") return true;
      if (target.isContentEditable) return true;
      return false;
    }

    function onKey(event: KeyboardEvent) {
      if (event.key.toLowerCase() !== shortcut.key.toLowerCase()) return;

      // When both meta and ctrl are requested, accept either modifier so
      // the same shortcut works on macOS (Cmd) and other platforms (Ctrl).
      const wantModifier = shortcut.meta || shortcut.ctrl;
      const hasModifier = event.metaKey || event.ctrlKey;
      if (wantModifier && !hasModifier) return;
      if (!wantModifier && hasModifier) return;

      if (shortcut.shift !== undefined && shortcut.shift !== event.shiftKey) return;
      if (shortcut.alt !== undefined && shortcut.alt !== event.altKey) return;
      if (isEditableTarget(event.target)) return;
      event.preventDefault();
      handler(event);
    }

    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [
    shortcut.key,
    shortcut.meta,
    shortcut.ctrl,
    shortcut.shift,
    shortcut.alt,
    handler,
    enabled,
  ]);
}
