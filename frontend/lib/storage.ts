"use client";

import { useEffect, useState } from "react";
import type { PracticeSettings, Profile, VocabItem } from "./types";

/** Bumped when the default seed list changes so users get fresh words without manual DevTools clears. */
const VOCAB_KEY = "linguistos.vocab.v2";
const SETTINGS_KEY = "linguistos.settings.v2";
const PROFILE_KEY = "linguistos.profile.v1";

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

  function updateVocab(id: string, patch: Partial<Omit<VocabItem, "id" | "createdAt">>) {
    setVocab((prev) =>
      prev.map((v) => (v.id === id ? { ...v, ...patch } : v)),
    );
  }

  function toggleLearned(id: string) {
    setVocab((prev) =>
      prev.map((v) => (v.id === id ? { ...v, learned: !v.learned } : v)),
    );
  }

  function clearVocab() {
    setVocab([]);
  }

  return {
    vocab,
    hydrated,
    addVocab,
    removeVocab,
    updateVocab,
    toggleLearned,
    clearVocab,
  };
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

/** Default word bank for fresh installs (100 common basic/intermediate items). */
const SEED_VOCAB: VocabItem[] = [
  { id: "seed-001", word: "hola", translation: "hello", language: "es", tags: ["other"], learned: false, createdAt: 1735000000000 },
  { id: "seed-002", word: "adiós", translation: "goodbye", language: "es", tags: ["other"], learned: false, createdAt: 1735000000100 },
  { id: "seed-003", word: "gracias", translation: "thank you", language: "es", tags: ["other"], learned: false, createdAt: 1735000000200 },
  { id: "seed-004", word: "por favor", translation: "please", language: "es", tags: ["other"], learned: false, createdAt: 1735000000300 },
  { id: "seed-005", word: "sí", translation: "yes", language: "es", tags: ["other"], learned: false, createdAt: 1735000000400 },
  { id: "seed-006", word: "no", translation: "no", language: "es", tags: ["other"], learned: false, createdAt: 1735000000500 },
  { id: "seed-007", word: "casa", translation: "house", language: "es", tags: ["noun"], learned: false, createdAt: 1735000000600 },
  { id: "seed-008", word: "agua", translation: "water", language: "es", tags: ["noun"], learned: false, createdAt: 1735000000700 },
  { id: "seed-009", word: "pan", translation: "bread", language: "es", tags: ["noun"], learned: false, createdAt: 1735000000800 },
  { id: "seed-010", word: "leche", translation: "milk", language: "es", tags: ["noun"], learned: false, createdAt: 1735000000900 },
  { id: "seed-011", word: "café", translation: "coffee", language: "es", tags: ["noun"], learned: false, createdAt: 1735000001000 },
  { id: "seed-012", word: "comida", translation: "food", language: "es", tags: ["noun"], learned: false, createdAt: 1735000001100 },
  { id: "seed-013", word: "día", translation: "day", language: "es", tags: ["noun"], learned: false, createdAt: 1735000001200 },
  { id: "seed-014", word: "noche", translation: "night", language: "es", tags: ["noun"], learned: false, createdAt: 1735000001300 },
  { id: "seed-015", word: "año", translation: "year", language: "es", tags: ["noun"], learned: false, createdAt: 1735000001400 },
  { id: "seed-016", word: "semana", translation: "week", language: "es", tags: ["noun"], learned: false, createdAt: 1735000001500 },
  { id: "seed-017", word: "mes", translation: "month", language: "es", tags: ["noun"], learned: false, createdAt: 1735000001600 },
  { id: "seed-018", word: "hora", translation: "hour", language: "es", tags: ["noun"], learned: false, createdAt: 1735000001700 },
  { id: "seed-019", word: "minuto", translation: "minute", language: "es", tags: ["noun"], learned: false, createdAt: 1735000001800 },
  { id: "seed-020", word: "tiempo", translation: "time", language: "es", tags: ["noun"], learned: false, createdAt: 1735000001900 },
  { id: "seed-021", word: "trabajo", translation: "work / job", language: "es", tags: ["noun"], learned: false, createdAt: 1735000002000 },
  { id: "seed-022", word: "escuela", translation: "school", language: "es", tags: ["noun"], learned: false, createdAt: 1735000002100 },
  { id: "seed-023", word: "universidad", translation: "university", language: "es", tags: ["noun"], learned: false, createdAt: 1735000002200 },
  { id: "seed-024", word: "familia", translation: "family", language: "es", tags: ["noun"], learned: false, createdAt: 1735000002300 },
  { id: "seed-025", word: "amigo", translation: "friend", language: "es", tags: ["noun"], learned: false, createdAt: 1735000002400 },
  { id: "seed-026", word: "mujer", translation: "woman", language: "es", tags: ["noun"], learned: false, createdAt: 1735000002500 },
  { id: "seed-027", word: "hombre", translation: "man", language: "es", tags: ["noun"], learned: false, createdAt: 1735000002600 },
  { id: "seed-028", word: "niño", translation: "child", language: "es", tags: ["noun"], learned: false, createdAt: 1735000002700 },
  { id: "seed-029", word: "perro", translation: "dog", language: "es", tags: ["noun"], learned: false, createdAt: 1735000002800 },
  { id: "seed-030", word: "gato", translation: "cat", language: "es", tags: ["noun"], learned: false, createdAt: 1735000002900 },
  { id: "seed-031", word: "libro", translation: "book", language: "es", tags: ["noun"], learned: false, createdAt: 1735000003000 },
  { id: "seed-032", word: "ciudad", translation: "city", language: "es", tags: ["noun"], learned: false, createdAt: 1735000003100 },
  { id: "seed-033", word: "país", translation: "country", language: "es", tags: ["noun"], learned: false, createdAt: 1735000003200 },
  { id: "seed-034", word: "calle", translation: "street", language: "es", tags: ["noun"], learned: false, createdAt: 1735000003300 },
  { id: "seed-035", word: "coche", translation: "car", language: "es", tags: ["noun"], learned: false, createdAt: 1735000003400 },
  { id: "seed-036", word: "dinero", translation: "money", language: "es", tags: ["noun"], learned: false, createdAt: 1735000003500 },
  { id: "seed-037", word: "mercado", translation: "market", language: "es", tags: ["noun"], learned: false, createdAt: 1735000003600 },
  { id: "seed-038", word: "problema", translation: "problem", language: "es", tags: ["noun"], learned: false, createdAt: 1735000003700 },
  { id: "seed-039", word: "idea", translation: "idea", language: "es", tags: ["noun"], learned: false, createdAt: 1735000003800 },
  { id: "seed-040", word: "mundo", translation: "world", language: "es", tags: ["noun"], learned: false, createdAt: 1735000003900 },
  { id: "seed-041", word: "vida", translation: "life", language: "es", tags: ["noun"], learned: false, createdAt: 1735000004000 },
  { id: "seed-042", word: "persona", translation: "person", language: "es", tags: ["noun"], learned: false, createdAt: 1735000004100 },
  { id: "seed-043", word: "nombre", translation: "name", language: "es", tags: ["noun"], learned: false, createdAt: 1735000004200 },
  { id: "seed-044", word: "foto", translation: "photo", language: "es", tags: ["noun"], learned: false, createdAt: 1735000004300 },
  { id: "seed-045", word: "música", translation: "music", language: "es", tags: ["noun"], learned: false, createdAt: 1735000004400 },
  { id: "seed-046", word: "película", translation: "film", language: "es", tags: ["noun"], learned: false, createdAt: 1735000004500 },
  { id: "seed-047", word: "color", translation: "color", language: "es", tags: ["noun"], learned: false, createdAt: 1735000004600 },
  { id: "seed-048", word: "número", translation: "number", language: "es", tags: ["noun"], learned: false, createdAt: 1735000004700 },
  { id: "seed-049", word: "sol", translation: "sun", language: "es", tags: ["noun"], learned: false, createdAt: 1735000004800 },
  { id: "seed-050", word: "luna", translation: "moon", language: "es", tags: ["noun"], learned: false, createdAt: 1735000004900 },
  { id: "seed-051", word: "mar", translation: "sea", language: "es", tags: ["noun"], learned: false, createdAt: 1735000005000 },
  { id: "seed-052", word: "montaña", translation: "mountain", language: "es", tags: ["noun"], learned: false, createdAt: 1735000005100 },
  { id: "seed-053", word: "árbol", translation: "tree", language: "es", tags: ["noun"], learned: false, createdAt: 1735000005200 },
  { id: "seed-054", word: "flor", translation: "flower", language: "es", tags: ["noun"], learned: false, createdAt: 1735000005300 },
  { id: "seed-055", word: "animal", translation: "animal", language: "es", tags: ["noun"], learned: false, createdAt: 1735000005400 },
  { id: "seed-056", word: "comer", translation: "to eat", language: "es", tags: ["verb"], learned: false, createdAt: 1735000005500 },
  { id: "seed-057", word: "beber", translation: "to drink", language: "es", tags: ["verb"], learned: false, createdAt: 1735000005600 },
  { id: "seed-058", word: "hablar", translation: "to speak", language: "es", tags: ["verb"], learned: false, createdAt: 1735000005700 },
  { id: "seed-059", word: "escuchar", translation: "to listen", language: "es", tags: ["verb"], learned: false, createdAt: 1735000005800 },
  { id: "seed-060", word: "leer", translation: "to read", language: "es", tags: ["verb"], learned: false, createdAt: 1735000005900 },
  { id: "seed-061", word: "escribir", translation: "to write", language: "es", tags: ["verb"], learned: false, createdAt: 1735000006000 },
  { id: "seed-062", word: "estudiar", translation: "to study", language: "es", tags: ["verb"], learned: false, createdAt: 1735000006100 },
  { id: "seed-063", word: "trabajar", translation: "to work", language: "es", tags: ["verb"], learned: false, createdAt: 1735000006200 },
  { id: "seed-064", word: "vivir", translation: "to live", language: "es", tags: ["verb"], learned: false, createdAt: 1735000006300 },
  { id: "seed-065", word: "ir", translation: "to go", language: "es", tags: ["verb"], learned: false, createdAt: 1735000006400 },
  { id: "seed-066", word: "venir", translation: "to come", language: "es", tags: ["verb"], learned: false, createdAt: 1735000006500 },
  { id: "seed-067", word: "tener", translation: "to have", language: "es", tags: ["verb"], learned: false, createdAt: 1735000006600 },
  { id: "seed-068", word: "ser", translation: "to be", language: "es", tags: ["verb"], learned: false, createdAt: 1735000006700 },
  { id: "seed-069", word: "estar", translation: "to be", language: "es", tags: ["verb"], learned: false, createdAt: 1735000006800 },
  { id: "seed-070", word: "hacer", translation: "to do / to make", language: "es", tags: ["verb"], learned: false, createdAt: 1735000006900 },
  { id: "seed-071", word: "poder", translation: "can / to be able", language: "es", tags: ["verb"], learned: false, createdAt: 1735000007000 },
  { id: "seed-072", word: "querer", translation: "to want", language: "es", tags: ["verb"], learned: false, createdAt: 1735000007100 },
  { id: "seed-073", word: "necesitar", translation: "to need", language: "es", tags: ["verb"], learned: false, createdAt: 1735000007200 },
  { id: "seed-074", word: "gustar", translation: "to like", language: "es", tags: ["verb"], learned: false, createdAt: 1735000007300 },
  { id: "seed-075", word: "ayudar", translation: "to help", language: "es", tags: ["verb"], learned: false, createdAt: 1735000007400 },
  { id: "seed-076", word: "comprar", translation: "to buy", language: "es", tags: ["verb"], learned: false, createdAt: 1735000007500 },
  { id: "seed-077", word: "vender", translation: "to sell", language: "es", tags: ["verb"], learned: false, createdAt: 1735000007600 },
  { id: "seed-078", word: "abrir", translation: "to open", language: "es", tags: ["verb"], learned: false, createdAt: 1735000007700 },
  { id: "seed-079", word: "cerrar", translation: "to close", language: "es", tags: ["verb"], learned: false, createdAt: 1735000007800 },
  { id: "seed-080", word: "pensar", translation: "to think", language: "es", tags: ["verb"], learned: false, createdAt: 1735000007900 },
  { id: "seed-081", word: "correr", translation: "to run", language: "es", tags: ["verb"], learned: false, createdAt: 1735000008000 },
  { id: "seed-082", word: "grande", translation: "big", language: "es", tags: ["adjective"], learned: false, createdAt: 1735000008100 },
  { id: "seed-083", word: "pequeño", translation: "small", language: "es", tags: ["adjective"], learned: false, createdAt: 1735000008200 },
  { id: "seed-084", word: "bueno", translation: "good", language: "es", tags: ["adjective"], learned: false, createdAt: 1735000008300 },
  { id: "seed-085", word: "malo", translation: "bad", language: "es", tags: ["adjective"], learned: false, createdAt: 1735000008400 },
  { id: "seed-086", word: "nuevo", translation: "new", language: "es", tags: ["adjective"], learned: false, createdAt: 1735000008500 },
  { id: "seed-087", word: "viejo", translation: "old", language: "es", tags: ["adjective"], learned: false, createdAt: 1735000008600 },
  { id: "seed-088", word: "joven", translation: "young", language: "es", tags: ["adjective"], learned: false, createdAt: 1735000008700 },
  { id: "seed-089", word: "fácil", translation: "easy", language: "es", tags: ["adjective"], learned: false, createdAt: 1735000008800 },
  { id: "seed-090", word: "difícil", translation: "difficult", language: "es", tags: ["adjective"], learned: false, createdAt: 1735000008900 },
  { id: "seed-091", word: "importante", translation: "important", language: "es", tags: ["adjective"], learned: false, createdAt: 1735000009000 },
  { id: "seed-092", word: "feliz", translation: "happy", language: "es", tags: ["adjective"], learned: false, createdAt: 1735000009100 },
  { id: "seed-093", word: "triste", translation: "sad", language: "es", tags: ["adjective"], learned: false, createdAt: 1735000009200 },
  { id: "seed-094", word: "rápido", translation: "fast", language: "es", tags: ["adjective"], learned: false, createdAt: 1735000009300 },
  { id: "seed-095", word: "lento", translation: "slow", language: "es", tags: ["adjective"], learned: false, createdAt: 1735000009400 },
  { id: "seed-096", word: "caliente", translation: "hot", language: "es", tags: ["adjective"], learned: false, createdAt: 1735000009500 },
  { id: "seed-097", word: "frío", translation: "cold", language: "es", tags: ["adjective"], learned: false, createdAt: 1735000009600 },
  { id: "seed-098", word: "dulce", translation: "sweet", language: "es", tags: ["adjective"], learned: false, createdAt: 1735000009700 },
  { id: "seed-099", word: "aquí", translation: "here", language: "es", tags: ["adverb"], learned: false, createdAt: 1735000009800 },
  { id: "seed-100", word: "mañana", translation: "tomorrow / morning", language: "es", tags: ["adverb"], learned: false, createdAt: 1735000009900 },
];
