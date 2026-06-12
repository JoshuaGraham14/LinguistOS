"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import * as api from "./api";
import { pollVocabEnrichedOnce } from "./vocabPoll";
import type {
  LanguageCode,
  MasteryOutcome,
  MasteryState,
  PracticeSettings,
  Profile,
  SavedView,
  SavedViewLayout,
  VocabItem,
  VocabTag,
  WordDisplayMode,
  Workspace,
} from "./types";
import type { VocabViewConfig } from "./vocab-view";

const SETTINGS_KEY = "linguistos.settings.v3";
const PROFILE_KEY = "linguistos.profile.v1";
const ACTIVE_WORKSPACE_KEY = "linguistos.workspace.active.v1";
const WORKSPACE_CHANGE_EVENT = "linguistos:workspace-change";
const WORKSPACES_LIST_SYNC_EVENT = "linguistos:workspaces-list-sync";
const VOCAB_ADD_EVENT = "linguistos:vocab-add";
const VOCAB_UPDATE_EVENT = "linguistos:vocab-update";
const VOCAB_REMOVE_EVENT = "linguistos:vocab-remove";
const VOCAB_CLEAR_EVENT = "linguistos:vocab-clear";
const SAVED_VIEWS_SYNC_EVENT = "linguistos:saved-views-sync";

export type SidebarState = { width: number; collapsed: boolean };

const DEFAULT_SETTINGS: PracticeSettings = {
  mode: "typing",
  direction: "en-to-es",
  sentenceLength: "short",
  tagFilter: [],
  tense: "present",
  person: "3rd",
  number: "singular",
  lexiconConstraint: "off",
  stretchCount: 0,
  autoAdvance: false,
};

const DEFAULT_PROFILE: Profile = { name: "", wordDisplayMode: "as_encountered" };

/**
 * Single rendering helper for any surface that displays a word (LOS-107).
 * Returns the form to show as primary plus the counterpart form, so callers
 * can render both without ever reading raw vocab fields directly.
 */
export function formatWordDisplay(
  item: VocabItem,
  mode: WordDisplayMode,
): { primary: string; secondary: string | null } {
  const lemma = item.lemma ?? item.word;
  const surface = item.surfaceForm ?? item.word;
  if (mode === "lemma_first") {
    return {
      primary: lemma,
      secondary: surface !== lemma ? surface : null,
    };
  }
  return {
    primary: surface,
    secondary: lemma !== surface ? lemma : null,
  };
}
const DEFAULT_WORKSPACE: Pick<Workspace, "name" | "language" | "emojiOrFlag"> = {
  name: "Spanish core",
  language: "es",
  emojiOrFlag: "🇪🇸",
};

function read<T>(key: string, fallback: T): T {
  if (typeof window === "undefined") return fallback;
  try {
    const raw = window.localStorage.getItem(key);
    return raw ? (JSON.parse(raw) as T) : fallback;
  } catch {
    return fallback;
  }
}

function write<T>(key: string, value: T) {
  if (typeof window === "undefined") return;
  window.localStorage.setItem(key, JSON.stringify(value));
}

function broadcastWorkspaceList(list: Workspace[]) {
  window.dispatchEvent(
    new CustomEvent(WORKSPACES_LIST_SYNC_EVENT, { detail: list }),
  );
}

function broadcastVocabAdd(item: VocabItem) {
  window.dispatchEvent(new CustomEvent(VOCAB_ADD_EVENT, { detail: item }));
}

function broadcastVocabUpdate(item: VocabItem) {
  window.dispatchEvent(new CustomEvent(VOCAB_UPDATE_EVENT, { detail: item }));
}

function broadcastVocabRemove(id: number) {
  window.dispatchEvent(new CustomEvent(VOCAB_REMOVE_EVENT, { detail: id }));
}

function broadcastVocabClear() {
  window.dispatchEvent(new CustomEvent(VOCAB_CLEAR_EVENT));
}

export function useProfile() {
  const [profile, setProfile] = useState<Profile>(DEFAULT_PROFILE);
  const [hydrated, setHydrated] = useState(false);

  useEffect(() => {
    const stored = read<Partial<Profile>>(PROFILE_KEY, DEFAULT_PROFILE);
    // Migrate old profile shapes that pre-date wordDisplayMode (LOS-107).
    setProfile({
      name: stored.name ?? DEFAULT_PROFILE.name,
      wordDisplayMode:
        stored.wordDisplayMode ?? DEFAULT_PROFILE.wordDisplayMode,
    });
    setHydrated(true);
  }, []);

  useEffect(() => {
    if (hydrated) write(PROFILE_KEY, profile);
  }, [profile, hydrated]);

  return { profile, setProfile, hydrated };
}

export function useSidebarState(
  storageKey: string,
  defaultState: SidebarState,
) {
  const [state, setState] = useState<SidebarState>(defaultState);
  const [hydrated, setHydrated] = useState(false);

  useEffect(() => {
    const stored = read<Partial<SidebarState>>(storageKey, defaultState);
    setState({
      width: typeof stored.width === "number" ? stored.width : defaultState.width,
      collapsed:
        typeof stored.collapsed === "boolean" ? stored.collapsed : defaultState.collapsed,
    });
    setHydrated(true);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [storageKey]);

  useEffect(() => {
    if (hydrated) write(storageKey, state);
  }, [state, hydrated, storageKey]);

  const setWidth = useCallback(
    (width: number) => setState((prev) => ({ ...prev, width })),
    [],
  );
  const toggleCollapsed = useCallback(
    () => setState((prev) => ({ ...prev, collapsed: !prev.collapsed })),
    [],
  );
  const setCollapsed = useCallback(
    (collapsed: boolean) => setState((prev) => ({ ...prev, collapsed })),
    [],
  );

  return { state, setWidth, toggleCollapsed, setCollapsed, hydrated };
}

export function usePracticeSettings() {
  const [settings, setSettings] = useState<PracticeSettings>(DEFAULT_SETTINGS);
  const [hydrated, setHydrated] = useState(false);

  useEffect(() => {
    const stored = read<Partial<PracticeSettings>>(SETTINGS_KEY, DEFAULT_SETTINGS);
    // Merge in defaults so old localStorage entries pick up new settings
    // (e.g. lexiconConstraint added in LOS-502).
    setSettings({ ...DEFAULT_SETTINGS, ...stored });
    setHydrated(true);
  }, []);

  useEffect(() => {
    if (hydrated) write(SETTINGS_KEY, settings);
  }, [settings, hydrated]);

  return { settings, setSettings, hydrated };
}

export function useWorkspaces() {
  const [workspaces, setWorkspaces] = useState<Workspace[]>([]);
  const [activeWorkspaceId, setActiveWorkspaceIdState] = useState<number | null>(null);
  const [hydrated, setHydrated] = useState(false);
  const [loading, setLoading] = useState(true);
  const workspacesRef = useRef<Workspace[]>([]);
  workspacesRef.current = workspaces;

  const setActiveWorkspaceId = useCallback((workspaceId: number) => {
    setActiveWorkspaceIdState((prev) => {
      if (prev === workspaceId) return prev;
      write(ACTIVE_WORKSPACE_KEY, workspaceId);
      // Only broadcast when switching between real workspaces (not initial hydrate null→id).
      // Defer so we never dispatch during React render/commit (avoids cross-tree setState warnings).
      if (prev !== null) {
        queueMicrotask(() => {
          window.dispatchEvent(new CustomEvent(WORKSPACE_CHANGE_EVENT, { detail: workspaceId }));
        });
      }
      return workspaceId;
    });
  }, []);

  const refresh = useCallback(async () => {
    try {
      const items = await api.listWorkspaces();
      if (items.length === 0) {
        const created = await api.createWorkspace(DEFAULT_WORKSPACE);
        setWorkspaces([created]);
        setActiveWorkspaceId(created.id);
        return;
      }
      setWorkspaces(items);
      const saved = read<number | null>(ACTIVE_WORKSPACE_KEY, null);
      const selected =
        saved && items.some((w) => w.id === saved) ? saved : items[0]?.id ?? null;
      if (selected) setActiveWorkspaceId(selected);
    } catch {
      // Keep UI alive if backend is temporarily unavailable.
      setWorkspaces([]);
      setActiveWorkspaceIdState(null);
    }
  }, [setActiveWorkspaceId]);

  useEffect(() => {
    let mounted = true;
    (async () => {
      try {
        await refresh();
      } finally {
        if (mounted) {
          setHydrated(true);
          setLoading(false);
        }
      }
    })();
    return () => {
      mounted = false;
    };
  }, [refresh]);

  useEffect(() => {
    function handleWorkspaceChange(event: Event) {
      const workspaceId = (event as CustomEvent<number>).detail;
      if (typeof workspaceId === "number") {
        queueMicrotask(() => {
          setActiveWorkspaceIdState(workspaceId);
        });
      }
    }
    window.addEventListener(WORKSPACE_CHANGE_EVENT, handleWorkspaceChange);
    return () =>
      window.removeEventListener(WORKSPACE_CHANGE_EVENT, handleWorkspaceChange);
  }, []);

  useEffect(() => {
    function handleWorkspacesListSync(event: Event) {
      const list = (event as CustomEvent<Workspace[]>).detail;
      if (Array.isArray(list)) {
        setWorkspaces(list);
      }
    }
    window.addEventListener(WORKSPACES_LIST_SYNC_EVENT, handleWorkspacesListSync);
    return () =>
      window.removeEventListener(WORKSPACES_LIST_SYNC_EVENT, handleWorkspacesListSync);
  }, []);

  const createWorkspace = useCallback(
    async (input: { name: string; language: LanguageCode; emojiOrFlag: string }) => {
      const created = await api.createWorkspace(input);
      const next = [...workspacesRef.current, created];
      broadcastWorkspaceList(next);
      setActiveWorkspaceId(created.id);
      return created;
    },
    [setActiveWorkspaceId],
  );

  const renameWorkspace = useCallback(async (workspaceId: number, name: string) => {
    const updated = await api.renameWorkspace(workspaceId, name);
    const next = workspacesRef.current.map((w) =>
      w.id === workspaceId ? updated : w,
    );
    broadcastWorkspaceList(next);
    return updated;
  }, []);

  const deleteWorkspace = useCallback(async (workspaceId: number) => {
    await api.deleteWorkspace(workspaceId);
    const prev = workspacesRef.current;
    const next = prev.filter((w) => w.id !== workspaceId);
    broadcastWorkspaceList(next);
    setActiveWorkspaceIdState((activeId) => {
      if (activeId === workspaceId && next.length > 0) {
        const nid = next[0]!.id;
        write(ACTIVE_WORKSPACE_KEY, nid);
        queueMicrotask(() => {
          window.dispatchEvent(new CustomEvent(WORKSPACE_CHANGE_EVENT, { detail: nid }));
        });
        return nid;
      }
      return activeId;
    });
  }, []);

  const activeWorkspace = useMemo(
    () => workspaces.find((w) => w.id === activeWorkspaceId) ?? null,
    [workspaces, activeWorkspaceId],
  );

  return {
    workspaces,
    activeWorkspace,
    activeWorkspaceId,
    setActiveWorkspaceId,
    createWorkspace,
    renameWorkspace,
    deleteWorkspace,
    refresh,
    loading,
    hydrated,
  };
}

export function useVocab() {
  const {
    activeWorkspace,
    activeWorkspaceId,
    hydrated: workspacesHydrated,
  } = useWorkspaces();
  const [vocab, setVocab] = useState<VocabItem[]>([]);
  const [hydrated, setHydrated] = useState(false);
  const pollEnrichingItems = useCallback(
    (items: VocabItem[]) => {
      if (!activeWorkspace) return;
      for (const item of items) {
        if (!item.enriching) continue;
        void pollVocabEnrichedOnce(item.id, activeWorkspace.language)
          .then((enriched) => {
            setVocab((prev) =>
              prev.map((v) => (v.id === enriched.id ? enriched : v)),
            );
            broadcastVocabUpdate(enriched);
          })
          .catch(() => undefined);
      }
    },
    [activeWorkspace],
  );

  const refresh = useCallback(async () => {
    if (!activeWorkspaceId || !activeWorkspace) return;
    try {
      const items = await api.listVocab(activeWorkspaceId, activeWorkspace.language);
      setVocab(items);
      pollEnrichingItems(items);
    } catch {
      setVocab([]);
    }
  }, [activeWorkspaceId, activeWorkspace, pollEnrichingItems]);

  useEffect(() => {
    if (!workspacesHydrated || !activeWorkspaceId) return;
    let mounted = true;
    (async () => {
      try {
        await refresh();
      } catch {
        setVocab([]);
      }
      if (mounted) setHydrated(true);
    })();
    return () => {
      mounted = false;
    };
  }, [refresh, workspacesHydrated, activeWorkspaceId]);

  useEffect(() => {
    function handleVocabAdd(event: Event) {
      const item = (event as CustomEvent<VocabItem>).detail;
      if (!item || item.workspaceId !== activeWorkspaceId) return;
      setVocab((prev) => {
        if (prev.some((v) => v.id === item.id)) return prev;
        return [item, ...prev];
      });
    }
    function handleVocabUpdate(event: Event) {
      const item = (event as CustomEvent<VocabItem>).detail;
      if (!item || item.workspaceId !== activeWorkspaceId) return;
      setVocab((prev) => prev.map((v) => (v.id === item.id ? item : v)));
    }
    function handleVocabRemove(event: Event) {
      const id = (event as CustomEvent<number>).detail;
      if (typeof id !== "number") return;
      setVocab((prev) => prev.filter((v) => v.id !== id));
    }
    function handleVocabClear() {
      setVocab([]);
    }
    window.addEventListener(VOCAB_ADD_EVENT, handleVocabAdd);
    window.addEventListener(VOCAB_UPDATE_EVENT, handleVocabUpdate);
    window.addEventListener(VOCAB_REMOVE_EVENT, handleVocabRemove);
    window.addEventListener(VOCAB_CLEAR_EVENT, handleVocabClear);
    return () => {
      window.removeEventListener(VOCAB_ADD_EVENT, handleVocabAdd);
      window.removeEventListener(VOCAB_UPDATE_EVENT, handleVocabUpdate);
      window.removeEventListener(VOCAB_REMOVE_EVENT, handleVocabRemove);
      window.removeEventListener(VOCAB_CLEAR_EVENT, handleVocabClear);
    };
  }, [activeWorkspaceId]);

  const addVocab = useCallback(
    async (input: {
      word?: string;
      translation?: string;
      surfaceForm?: string;
      glossPrimary?: string;
      glosses?: string[];
      lemma?: string;
      tags?: VocabTag[];
      pos?: string | null;
      cefr?: string | null;
      frequencyRank?: number | null;
      gender?: string | null;
      conjugationClass?: string | null;
      morphFeatures?: Record<string, unknown> | null;
      ipa?: string | null;
      notes?: string | null;
    }) => {
      if (!activeWorkspaceId || !activeWorkspace) throw new Error("No active workspace");
      const item = await api.addVocab({
        workspaceId: activeWorkspaceId,
        language: activeWorkspace.language,
        surfaceForm: input.surfaceForm ?? input.word,
        glossPrimary: input.glossPrimary ?? input.translation,
        glosses: input.glosses,
        lemma: input.lemma,
        tags: input.tags ?? [],
        pos: input.pos ?? null,
        cefr: input.cefr ?? null,
        frequencyRank: input.frequencyRank ?? null,
        gender: input.gender ?? null,
        conjugationClass: input.conjugationClass ?? null,
        morphFeatures: input.morphFeatures ?? null,
        ipa: input.ipa ?? null,
        notes: input.notes ?? null,
        word: input.word,
        translation: input.translation,
      });
      setVocab((prev) => [item, ...prev]);
      broadcastVocabAdd(item);
      if (item.enriching) {
        void pollVocabEnrichedOnce(item.id, activeWorkspace.language)
          .then((enriched) => {
            setVocab((prev) =>
              prev.map((v) => (v.id === enriched.id ? enriched : v)),
            );
            broadcastVocabUpdate(enriched);
          })
          .catch(() => undefined);
      }
      return item;
    },
    [activeWorkspaceId, activeWorkspace],
  );

  const removeVocab = useCallback(async (id: number) => {
    await api.removeVocab(id);
    setVocab((prev) => prev.filter((v) => v.id !== id));
    broadcastVocabRemove(id);
  }, []);

  const updateVocab = useCallback(
    async (id: number, patch: api.UpdateVocabPatch) => {
      if (!activeWorkspace) throw new Error("No active workspace");
      const updated = await api.updateVocab(id, patch, activeWorkspace.language);
      setVocab((prev) => prev.map((v) => (v.id === id ? updated : v)));
      broadcastVocabUpdate(updated);
      return updated;
    },
    [activeWorkspace],
  );

  const toggleLearned = useCallback(
    async (id: number) => {
      const existing = vocab.find((v) => v.id === id);
      if (!existing) return;
      await updateVocab(id, { learned: !existing.learned });
    },
    [vocab, updateVocab],
  );

  const clearVocab = useCallback(async () => {
    if (!activeWorkspaceId) return;
    await api.clearVocab(activeWorkspaceId);
    setVocab([]);
    broadcastVocabClear();
  }, [activeWorkspaceId]);

  /**
   * Record a review outcome against the canonical mastery state (LOS-901).
   * Optimistically merges the returned mastery into local vocab so views
   * reflect the new strength/box/next_due immediately.
   */
  const recordOutcome = useCallback(
    async (
      id: number,
      outcome: MasteryOutcome,
      source = "practice",
    ): Promise<MasteryState | null> => {
      try {
        const next = await api.recordMasteryEvent(id, outcome, source);
        setVocab((prev) =>
          prev.map((v) => (v.id === id ? { ...v, mastery: next } : v)),
        );
        return next;
      } catch {
        return null;
      }
    },
    [],
  );

  return {
    vocab,
    hydrated: hydrated && workspacesHydrated,
    addVocab,
    removeVocab,
    updateVocab,
    toggleLearned,
    clearVocab,
    refresh,
    recordOutcome,
    activeWorkspace,
  };
}

function broadcastSavedViews(list: SavedView[]) {
  window.dispatchEvent(
    new CustomEvent(SAVED_VIEWS_SYNC_EVENT, { detail: list }),
  );
}

export function useSavedViews() {
  const { activeWorkspaceId, hydrated: workspacesHydrated } = useWorkspaces();
  const [views, setViews] = useState<SavedView[]>([]);
  const [hydrated, setHydrated] = useState(false);
  const [loading, setLoading] = useState(true);
  const viewsRef = useRef<SavedView[]>([]);
  viewsRef.current = views;

  const refresh = useCallback(async () => {
    if (!activeWorkspaceId) {
      setViews([]);
      return;
    }
    const items = await api.listSavedViews(activeWorkspaceId);
    setViews(items);
    broadcastSavedViews(items);
  }, [activeWorkspaceId]);

  useEffect(() => {
    if (!workspacesHydrated) return;
    let mounted = true;
    (async () => {
      setLoading(true);
      try {
        if (activeWorkspaceId) await refresh();
        else setViews([]);
      } catch {
        if (mounted) setViews([]);
      } finally {
        if (mounted) {
          setHydrated(true);
          setLoading(false);
        }
      }
    })();
    return () => {
      mounted = false;
    };
  }, [activeWorkspaceId, workspacesHydrated, refresh]);

  useEffect(() => {
    function handleSync(event: Event) {
      const list = (event as CustomEvent<SavedView[]>).detail;
      if (Array.isArray(list)) setViews(list);
    }
    window.addEventListener(SAVED_VIEWS_SYNC_EVENT, handleSync);
    return () => window.removeEventListener(SAVED_VIEWS_SYNC_EVENT, handleSync);
  }, []);

  const createView = useCallback(
    async (input: {
      name: string;
      icon?: string | null;
      layout?: SavedViewLayout;
      config?: VocabViewConfig;
      position?: number;
    }) => {
      if (!activeWorkspaceId) throw new Error("No active workspace");
      const created = await api.createSavedView({
        workspaceId: activeWorkspaceId,
        ...input,
      });
      const next = [...viewsRef.current, created].sort(
        (a, b) => a.position - b.position || a.id - b.id,
      );
      broadcastSavedViews(next);
      return created;
    },
    [activeWorkspaceId],
  );

  const patchView = useCallback(
    async (
      viewId: number,
      patch: {
        name?: string;
        icon?: string | null;
        layout?: SavedViewLayout;
        config?: VocabViewConfig;
        position?: number;
      },
    ) => {
      const updated = await api.updateSavedView(viewId, patch);
      const next = viewsRef.current
        .map((v) => (v.id === viewId ? updated : v))
        .sort((a, b) => a.position - b.position || a.id - b.id);
      broadcastSavedViews(next);
      return updated;
    },
    [],
  );

  const removeView = useCallback(async (viewId: number) => {
    await api.deleteSavedView(viewId);
    const next = viewsRef.current.filter((v) => v.id !== viewId);
    broadcastSavedViews(next);
  }, []);

  return {
    views,
    hydrated: hydrated && workspacesHydrated,
    loading,
    refresh,
    createView,
    patchView,
    removeView,
  };
}
