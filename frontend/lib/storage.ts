"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import * as api from "./api";
import type {
  LanguageCode,
  PracticeSettings,
  Profile,
  VocabItem,
  VocabTag,
  Workspace,
} from "./types";

const SETTINGS_KEY = "linguistos.settings.v2";
const PROFILE_KEY = "linguistos.profile.v1";
const ACTIVE_WORKSPACE_KEY = "linguistos.workspace.active.v1";
const WORKSPACE_CHANGE_EVENT = "linguistos:workspace-change";

const DEFAULT_SETTINGS: PracticeSettings = {
  mode: "typing",
  direction: "en-to-es",
  sentenceLength: "short",
  tagFilter: [],
  tense: "present",
  person: "3rd",
  number: "singular",
};

const DEFAULT_PROFILE: Profile = { name: "" };
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

export function useProfile() {
  const [profile, setProfile] = useState<Profile>(DEFAULT_PROFILE);
  const [hydrated, setHydrated] = useState(false);

  useEffect(() => {
    setProfile(read<Profile>(PROFILE_KEY, DEFAULT_PROFILE));
    setHydrated(true);
  }, []);

  useEffect(() => {
    if (hydrated) write(PROFILE_KEY, profile);
  }, [profile, hydrated]);

  return { profile, setProfile, hydrated };
}

export function usePracticeSettings() {
  const [settings, setSettings] = useState<PracticeSettings>(DEFAULT_SETTINGS);
  const [hydrated, setHydrated] = useState(false);

  useEffect(() => {
    setSettings(read<PracticeSettings>(SETTINGS_KEY, DEFAULT_SETTINGS));
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

  const setActiveWorkspaceId = useCallback((workspaceId: number) => {
    setActiveWorkspaceIdState(workspaceId);
    write(ACTIVE_WORKSPACE_KEY, workspaceId);
    window.dispatchEvent(new CustomEvent(WORKSPACE_CHANGE_EVENT, { detail: workspaceId }));
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
        setActiveWorkspaceIdState(workspaceId);
      }
    }
    window.addEventListener(WORKSPACE_CHANGE_EVENT, handleWorkspaceChange);
    return () =>
      window.removeEventListener(WORKSPACE_CHANGE_EVENT, handleWorkspaceChange);
  }, []);

  const createWorkspace = useCallback(
    async (input: { name: string; language: LanguageCode; emojiOrFlag: string }) => {
      const created = await api.createWorkspace(input);
      setWorkspaces((prev) => [...prev, created]);
      setActiveWorkspaceId(created.id);
      return created;
    },
    [setActiveWorkspaceId],
  );

  const renameWorkspace = useCallback(async (workspaceId: number, name: string) => {
    const updated = await api.renameWorkspace(workspaceId, name);
    setWorkspaces((prev) => prev.map((w) => (w.id === workspaceId ? updated : w)));
    return updated;
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
    async (input: { word: string; translation: string; tags: VocabTag[] }) => {
      if (!activeWorkspaceId || !activeWorkspace) throw new Error("No active workspace");
      const item = await api.addVocab({
        workspaceId: activeWorkspaceId,
        word: input.word,
        translation: input.translation,
        tags: input.tags,
        language: activeWorkspace.language,
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
    async (
      id: number,
      patch: Partial<Pick<VocabItem, "word" | "translation" | "tags" | "learned">>,
    ) => {
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

  return {
    vocab,
    hydrated: hydrated && workspacesHydrated,
    addVocab,
    removeVocab,
    updateVocab,
    toggleLearned,
    clearVocab,
    refresh,
    activeWorkspace,
  };
}
