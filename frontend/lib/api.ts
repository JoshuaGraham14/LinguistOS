import type { SentenceCandidate } from "./types";

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
