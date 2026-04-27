"use client";

import { useEffect, useState } from "react";
import type { PracticeSettings, VocabItem } from "./types";

const VOCAB_KEY = "linguistos.vocab.v1";
const SETTINGS_KEY = "linguistos.settings.v1";

const DEFAULT_SETTINGS: PracticeSettings = {
  mode: "typing",
  direction: "en-to-es",
  sentenceLength: "short",
  tagFilter: [],
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

export function useVocab() {
  const [vocab, setVocab] = useState<VocabItem[]>([]);
  const [hydrated, setHydrated] = useState(false);

  useEffect(() => {
    setVocab(read<VocabItem[]>(VOCAB_KEY, SEED_VOCAB));
    setHydrated(true);
  }, []);

  useEffect(() => {
    if (hydrated) write(VOCAB_KEY, vocab);
  }, [vocab, hydrated]);

  function addVocab(input: Omit<VocabItem, "id" | "createdAt" | "learned" | "language">) {
    const item: VocabItem = {
      id: crypto.randomUUID(),
      createdAt: Date.now(),
      learned: false,
      language: "es",
      ...input,
    };
    setVocab((prev) => [item, ...prev]);
    return item;
  }

  function removeVocab(id: string) {
    setVocab((prev) => prev.filter((v) => v.id !== id));
  }

  function toggleLearned(id: string) {
    setVocab((prev) =>
      prev.map((v) => (v.id === id ? { ...v, learned: !v.learned } : v)),
    );
  }

  return { vocab, hydrated, addVocab, removeVocab, toggleLearned };
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

const SEED_VOCAB: VocabItem[] = [
  {
    id: "seed-1",
    word: "olor",
    translation: "smell",
    language: "es",
    tags: ["noun"],
    learned: false,
    createdAt: Date.now(),
  },
  {
    id: "seed-2",
    word: "dulce",
    translation: "sweet",
    language: "es",
    tags: ["adjective"],
    learned: true,
    createdAt: Date.now(),
  },
  {
    id: "seed-3",
    word: "correr",
    translation: "to run",
    language: "es",
    tags: ["verb"],
    learned: false,
    createdAt: Date.now(),
  },
];
