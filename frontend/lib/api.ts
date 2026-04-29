import type {
  LanguageCode,
  SentenceCandidate,
  VocabItem,
  VocabTag,
  Workspace,
} from "./types";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

async function apiFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_URL}${path}`, {
    headers: { "Content-Type": "application/json", ...(init?.headers ?? {}) },
    ...init,
  });
  if (!res.ok) throw new Error(`API ${res.status}: ${await res.text()}`);
  return res.json() as Promise<T>;
}

export interface GenerateRequest {
  word: string;
  translation: string;
  tense: string;
  person: string;
  number: string;
  num_candidates?: number;
  sentence_length?: string;
  direction?: string;
}

export interface GenerateResponse {
  candidates: SentenceCandidate[];
  mock?: boolean;
}

export async function generateSentences(
  params: GenerateRequest,
): Promise<GenerateResponse> {
  return apiFetch<GenerateResponse>("/api/generate", {
    method: "POST",
    body: JSON.stringify(params),
  });
}

const MOCK_BANK: Record<string, { sentence: string; translation: string }[]> = {
  correr: [
    { sentence: "Ella corre por el parque cada mañana.", translation: "She runs through the park every morning." },
    { sentence: "Los niños corren hacia la escuela.", translation: "The children run toward the school." },
    { sentence: "Yo corrí diez kilómetros ayer.", translation: "I ran ten kilometers yesterday." },
  ],
  olor: [
    { sentence: "El olor del pan recién hecho llena la cocina.", translation: "The smell of freshly baked bread fills the kitchen." },
    { sentence: "Me encanta el olor de las flores en primavera.", translation: "I love the smell of flowers in spring." },
  ],
  dulce: [
    { sentence: "La fruta está muy dulce hoy.", translation: "The fruit is very sweet today." },
    { sentence: "Su voz es dulce y tranquila.", translation: "Her voice is sweet and calm." },
  ],
};

const FALLBACK = [
  {
    sentence: "Hoy el día está soleado y cálido.",
    translation: "Today the day is sunny and warm.",
  },
  {
    sentence: "Mi amigo siempre llega tarde a la fiesta.",
    translation: "My friend always arrives late to the party.",
  },
];

export function mockGenerate(req: GenerateRequest): GenerateResponse {
  const bank = MOCK_BANK[req.word.toLowerCase()] ?? FALLBACK;
  const candidates = bank.slice(0, req.num_candidates ?? 3).map((c, i) => ({
    sentence: c.sentence,
    translation: c.translation,
    score: 4 - i * 0.5,
  }));
  return { candidates, mock: true };
}

export async function generateOrMock(
  req: GenerateRequest,
): Promise<GenerateResponse> {
  try {
    const res = await generateSentences(req);
    if (!res.candidates || res.candidates.length === 0) {
      return mockGenerate(req);
    }
    return res;
  } catch {
    return mockGenerate(req);
  }
}

interface ApiWorkspace {
  id: number;
  owner_id: number;
  name: string;
  language: LanguageCode;
  emoji_or_flag: string;
  created_at: string;
  updated_at: string;
}

interface ApiVocab {
  id: number;
  workspace_id: number;
  word: string;
  translation: string;
  tags: VocabTag[];
  learned: boolean;
  created_at: string;
}

function toWorkspace(item: ApiWorkspace): Workspace {
  return {
    id: item.id,
    ownerId: item.owner_id,
    name: item.name,
    language: item.language,
    emojiOrFlag: item.emoji_or_flag,
    createdAt: Date.parse(item.created_at),
    updatedAt: Date.parse(item.updated_at),
  };
}

function toVocab(item: ApiVocab, language: LanguageCode): VocabItem {
  return {
    id: item.id,
    workspaceId: item.workspace_id,
    word: item.word,
    translation: item.translation,
    language,
    tags: item.tags,
    learned: item.learned,
    createdAt: Date.parse(item.created_at),
  };
}

export async function listWorkspaces(): Promise<Workspace[]> {
  const items = await apiFetch<ApiWorkspace[]>("/api/workspaces");
  return items.map(toWorkspace);
}

export async function createWorkspace(input: {
  name: string;
  language: LanguageCode;
  emojiOrFlag: string;
}): Promise<Workspace> {
  const item = await apiFetch<ApiWorkspace>("/api/workspaces", {
    method: "POST",
    body: JSON.stringify({
      name: input.name,
      language: input.language,
      emoji_or_flag: input.emojiOrFlag,
    }),
  });
  return toWorkspace(item);
}

export async function renameWorkspace(
  workspaceId: number,
  name: string,
): Promise<Workspace> {
  const item = await apiFetch<ApiWorkspace>(`/api/workspaces/${workspaceId}`, {
    method: "PATCH",
    body: JSON.stringify({ name }),
  });
  return toWorkspace(item);
}

export async function listVocab(
  workspaceId: number,
  language: LanguageCode,
): Promise<VocabItem[]> {
  const res = await apiFetch<{ items: ApiVocab[] }>(
    `/api/vocab?workspace_id=${workspaceId}`,
  );
  return res.items.map((item) => toVocab(item, language));
}

export async function addVocab(input: {
  workspaceId: number;
  word: string;
  translation: string;
  tags: VocabTag[];
  language: LanguageCode;
}): Promise<VocabItem> {
  const item = await apiFetch<ApiVocab>("/api/vocab", {
    method: "POST",
    body: JSON.stringify({
      workspace_id: input.workspaceId,
      word: input.word,
      translation: input.translation,
      tags: input.tags,
    }),
  });
  return toVocab(item, input.language);
}

export async function updateVocab(
  vocabId: number,
  patch: Partial<Pick<VocabItem, "word" | "translation" | "tags" | "learned">>,
  language: LanguageCode,
): Promise<VocabItem> {
  const item = await apiFetch<ApiVocab>(`/api/vocab/${vocabId}`, {
    method: "PATCH",
    body: JSON.stringify(patch),
  });
  return toVocab(item, language);
}

export async function removeVocab(vocabId: number): Promise<void> {
  await apiFetch<{ ok: boolean }>(`/api/vocab/${vocabId}`, {
    method: "DELETE",
  });
}

export async function clearVocab(workspaceId: number): Promise<void> {
  await apiFetch<{ ok: boolean }>(`/api/vocab?workspace_id=${workspaceId}`, {
    method: "DELETE",
  });
}
