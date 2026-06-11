"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import type { SavedView } from "./types";
import type { VocabViewConfig } from "./vocab-view";

export type ViewSaveStatus = "idle" | "saving" | "saved" | "error";

const DEBOUNCE_MS = 500;

export function useDebouncedViewPatch(
  view: SavedView | null,
  patchView: (
    viewId: number,
    patch: { config: VocabViewConfig },
  ) => Promise<SavedView>,
) {
  const [config, setConfigState] = useState<VocabViewConfig | null>(
    view?.config ?? null,
  );
  const [saveStatus, setSaveStatus] = useState<ViewSaveStatus>("idle");
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const abortRef = useRef<AbortController | null>(null);
  const pendingRef = useRef<VocabViewConfig | null>(null);
  const viewIdRef = useRef<number | null>(view?.id ?? null);

  const persist = useCallback(
    async (viewId: number, nextConfig: VocabViewConfig) => {
      abortRef.current?.abort();
      const controller = new AbortController();
      abortRef.current = controller;
      setSaveStatus("saving");
      try {
        await patchView(viewId, { config: nextConfig });
        if (controller.signal.aborted) return;
        setSaveStatus("saved");
        pendingRef.current = null;
      } catch {
        if (!controller.signal.aborted) setSaveStatus("error");
      }
    },
    [patchView],
  );

  const flush = useCallback(async () => {
    if (timerRef.current) {
      clearTimeout(timerRef.current);
      timerRef.current = null;
    }
    const viewId = viewIdRef.current;
    const pending = pendingRef.current;
    if (viewId == null || pending == null) return;
    await persist(viewId, pending);
  }, [persist]);

  const schedulePatch = useCallback(
    (nextConfig: VocabViewConfig) => {
      pendingRef.current = nextConfig;
      if (timerRef.current) clearTimeout(timerRef.current);
      timerRef.current = setTimeout(() => {
        timerRef.current = null;
        const viewId = viewIdRef.current;
        const pending = pendingRef.current;
        if (viewId != null && pending != null) {
          void persist(viewId, pending);
        }
      }, DEBOUNCE_MS);
    },
    [persist],
  );

  const setConfig = useCallback(
    (updater: VocabViewConfig | ((prev: VocabViewConfig) => VocabViewConfig)) => {
      setConfigState((prev) => {
        if (!prev) return prev;
        const next = typeof updater === "function" ? updater(prev) : updater;
        schedulePatch(next);
        return next;
      });
    },
    [schedulePatch],
  );

  useEffect(() => {
    const nextId = view?.id ?? null;
    if (nextId !== viewIdRef.current) {
      void (async () => {
        await flush();
        viewIdRef.current = nextId;
        setConfigState(view?.config ?? null);
        setSaveStatus("idle");
        pendingRef.current = null;
      })();
    } else if (view?.config && config == null) {
      setConfigState(view.config);
    }
  }, [view, flush, config]);

  useEffect(() => {
    return () => {
      if (timerRef.current) clearTimeout(timerRef.current);
      abortRef.current?.abort();
    };
  }, []);

  return { config, setConfig, flush, saveStatus };
}
