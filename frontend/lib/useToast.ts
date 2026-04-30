"use client";

import { useCallback, useEffect, useState } from "react";

/**
 * Tiny self-clearing toast state. Multiple components can each own a
 * local toast without coordinating; the screen position is controlled
 * by the caller's render output.
 */
export function useToast(durationMs = 2200): {
  toast: string | null;
  showToast: (message: string) => void;
} {
  const [toast, setToast] = useState<string | null>(null);

  const showToast = useCallback((message: string) => {
    setToast(message);
  }, []);

  useEffect(() => {
    if (!toast) return;
    const id = window.setTimeout(() => setToast(null), durationMs);
    return () => window.clearTimeout(id);
  }, [toast, durationMs]);

  return { toast, showToast };
}
