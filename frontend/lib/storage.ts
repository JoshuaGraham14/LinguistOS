"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import * as api from "./api";
import type {
  LanguageCode,
  MasteryOutcome,
  MasteryState,
  PracticeSettings,
  Profile,
  VocabItem,
  VocabTag,
  WordDisplayMode,
  Workspace,
} from "./types";

const SETTINGS_KEY = "linguistos.settings.v3";
const PROFILE_KEY = "linguistos.profile.v1";
const ACTIVE_WORKSPACE_KEY = "linguistos.workspace.active.v1";
const WORKSPACE_CHANGE_EVENT = "linguistos:workspace-change";
const WORKSPACES_LIST_SYNC_EVENT = "linguistos:workspaces-list-sync";

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

  const refresh = useCallback(async () => {
    if (!activeWorkspaceId || !activeWorkspace) return;
    try {
      const items = await api.listVocab(activeWorkspaceId, activeWorkspace.language);
      setVocab(items);
    } catch {
      setVocab([]);
    }
  }, [activeWorkspaceId, activeWorkspace]);

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

  const addVocab = useCallback(
    async (input: {
      word?: string;
      translation?: string;
      surfaceForm?: string;
      glossPrimary?: string;
      tags?: VocabTag[];
      pos?: string | null;
      notes?: string | null;
    }) => {
      if (!activeWorkspaceId || !activeWorkspace) throw new Error("No active workspace");
      const item = await api.addVocab({
        workspaceId: activeWorkspaceId,
        language: activeWorkspace.language,
        surfaceForm: input.surfaceForm ?? input.word,
        glossPrimary: input.glossPrimary ?? input.translation,
        tags: input.tags ?? [],
        pos: input.pos ?? null,
        notes: input.notes ?? null,
        word: input.word,
        translation: input.translation,
      });
      setVocab((prev) => [item, ...prev]);
      return item;
    },
    [activeWorkspaceId, activeWorkspace],
  );

  const removeVocab = useCallback(async (id: number) => {
    await api.removeVocab(id);
    setVocab((prev) => prev.filter((v) => v.id !== id));
  }, []);

  const updateVocab = useCallback(
    async (id: number, patch: api.UpdateVocabPatch) => {
      if (!activeWorkspace) throw new Error("No active workspace");
      const updated = await api.updateVocab(id, patch, activeWorkspace.language);
      setVocab((prev) => prev.map((v) => (v.id === id ? updated : v)));
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
