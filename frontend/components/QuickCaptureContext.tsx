"use client";

import {
  createContext,
  useCallback,
  useContext,
  useMemo,
  useState,
  type ReactNode,
} from "react";

export type QuickCaptureContextValue = {
  open: boolean;
  openCapture: () => void;
  closeCapture: () => void;
};

const QuickCaptureContext = createContext<QuickCaptureContextValue | null>(null);

export function QuickCaptureProvider({ children }: { children: ReactNode }) {
  const [open, setOpen] = useState(false);
  const openCapture = useCallback(() => setOpen(true), []);
  const closeCapture = useCallback(() => setOpen(false), []);
  const value = useMemo(
    () => ({ open, openCapture, closeCapture }),
    [open, openCapture, closeCapture],
  );
  return (
    <QuickCaptureContext.Provider value={value}>{children}</QuickCaptureContext.Provider>
  );
}

export function useQuickCapture() {
  const ctx = useContext(QuickCaptureContext);
  if (!ctx) {
    throw new Error("useQuickCapture must be used within QuickCaptureProvider");
  }
  return ctx;
}
