import type {
  LanguageCode,
  LexiconConstraint,
  MasteryOutcome,
  MasteryState,
  SentenceCandidate,
  SentenceLink,
  SentenceLinkRole,
  SentenceRecord,
  SentenceSource,
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
  // LOS-502 lexicon constraint.
  lexicon_constraint?: LexiconConstraint;
  workspace_id?: number;
  stretch_count?: number;
  extra_allowed_vocab_ids?: number[];
}

export interface GenerateResponse {
  candidates: SentenceCandidate[];
  mock?: boolean;
  constrained?: boolean;
  used_vocab_ids?: number[];
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

interface ApiMastery {
  strength: number;
  box: number;
  last_reviewed_at: string | null;
  next_due: string | null;
  streak: number;
  failures: number;
  successes: number;
}

interface ApiVocab {
  id: number;
  workspace_id: number;
  word: string;
  translation: string;
  tags: VocabTag[];
  learned: boolean;
  created_at: string;

  lemma: string | null;
  surface_form: string | null;
  surface_forms: string[];
  pos: string | null;
  cefr: string | null;
  frequency_rank: number | null;
  gender: string | null;
  conjugation_class: string | null;
  morph_features: Record<string, unknown> | null;
  ipa: string | null;
  audio_url: string | null;
  image_url: string | null;
  gloss_primary: string | null;
  glosses: string[];
  notes: string | null;
  last_seen_at: string | null;

  mastery: ApiMastery | null;
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

function toMastery(item: ApiMastery): MasteryState {
  return {
    strength: item.strength,
    box: item.box,
    lastReviewedAt: item.last_reviewed_at ? Date.parse(item.last_reviewed_at) : null,
    nextDue: item.next_due ? Date.parse(item.next_due) : null,
    streak: item.streak,
    failures: item.failures,
    successes: item.successes,
  };
}

function toMasteryOrNull(item: ApiMastery | null): MasteryState | null {
  return item ? toMastery(item) : null;
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
    lemma: item.lemma,
    surfaceForm: item.surface_form,
    surfaceForms: item.surface_forms ?? [],
    pos: item.pos,
    cefr: item.cefr,
    frequencyRank: item.frequency_rank,
    gender: item.gender,
    conjugationClass: item.conjugation_class,
    morphFeatures: item.morph_features,
    ipa: item.ipa,
    audioUrl: item.audio_url,
    imageUrl: item.image_url,
    glossPrimary: item.gloss_primary,
    glosses: item.glosses ?? [],
    notes: item.notes,
    lastSeenAt: item.last_seen_at ? Date.parse(item.last_seen_at) : null,
    mastery: toMasteryOrNull(item.mastery),
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

export async function deleteWorkspace(workspaceId: number): Promise<void> {
  const res = await fetch(`${API_URL}/api/workspaces/${workspaceId}`, {
    method: "DELETE",
    headers: { "Content-Type": "application/json" },
  });
  if (!res.ok) {
    const text = await res.text();
    throw new Error(`API ${res.status}: ${text || res.statusText}`);
  }
  // Server returns 204 No Content with an empty body — do not call res.json().
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

export interface AddVocabInput {
  workspaceId: number;
  language: LanguageCode;
  // Canonical (preferred): only surfaceForm is required (LOS-106).
  surfaceForm?: string;
  glossPrimary?: string;
  lemma?: string;
  pos?: string | null;
  tags?: VocabTag[];
  notes?: string | null;
  // Legacy support: callers passing { word, translation } still work.
  word?: string;
  translation?: string;
}

export async function addVocab(input: AddVocabInput): Promise<VocabItem> {
  const surface = input.surfaceForm ?? input.word;
  if (!surface) {
    throw new Error("addVocab requires either surfaceForm or word");
  }
  const gloss = (input.glossPrimary ?? input.translation ?? "").trim();
  const item = await apiFetch<ApiVocab>("/api/vocab", {
    method: "POST",
    body: JSON.stringify({
      workspace_id: input.workspaceId,
      surface_form: surface,
      lemma: input.lemma,
      pos: input.pos ?? null,
      tags: input.tags ?? [],
      notes: input.notes ?? null,
      // Mirror legacy fields so existing list/render paths keep working
      // until the adapter retirement criteria are met.
      word: surface,
      ...(gloss
        ? {
            gloss_primary: gloss,
            translation: gloss,
          }
        : {}),
    }),
  });
  return toVocab(item, input.language);
}

export interface UpdateVocabPatch {
  word?: string;
  translation?: string;
  tags?: VocabTag[];
  learned?: boolean;
  surfaceForm?: string;
  lemma?: string;
  pos?: string | null;
  cefr?: string | null;
  glossPrimary?: string | null;
  glosses?: string[];
  notes?: string | null;
  audioUrl?: string | null;
  imageUrl?: string | null;
}

export async function updateVocab(
  vocabId: number,
  patch: UpdateVocabPatch,
  language: LanguageCode,
): Promise<VocabItem> {
  const body: Record<string, unknown> = {};
  if (patch.word !== undefined) body.word = patch.word;
  if (patch.translation !== undefined) body.translation = patch.translation;
  if (patch.tags !== undefined) body.tags = patch.tags;
  if (patch.learned !== undefined) body.learned = patch.learned;
  if (patch.surfaceForm !== undefined) body.surface_form = patch.surfaceForm;
  if (patch.lemma !== undefined) body.lemma = patch.lemma;
  if (patch.pos !== undefined) body.pos = patch.pos;
  if (patch.cefr !== undefined) body.cefr = patch.cefr;
  if (patch.glossPrimary !== undefined) body.gloss_primary = patch.glossPrimary;
  if (patch.glosses !== undefined) body.glosses = patch.glosses;
  if (patch.notes !== undefined) body.notes = patch.notes;
  if (patch.audioUrl !== undefined) body.audio_url = patch.audioUrl;
  if (patch.imageUrl !== undefined) body.image_url = patch.imageUrl;

  const item = await apiFetch<ApiVocab>(`/api/vocab/${vocabId}`, {
    method: "PATCH",
    body: JSON.stringify(body),
  });
  return toVocab(item, language);
}

export async function getVocab(
  vocabId: number,
  language: LanguageCode,
): Promise<VocabItem> {
  const item = await apiFetch<ApiVocab>(`/api/vocab/${vocabId}`);
  return toVocab(item, language);
}

export async function recordMasteryEvent(
  vocabId: number,
  outcome: MasteryOutcome,
  source = "practice",
): Promise<MasteryState> {
  const m = await apiFetch<ApiMastery>(
    `/api/vocab/${vocabId}/mastery/event`,
    {
      method: "POST",
      body: JSON.stringify({ outcome, source }),
    },
  );
  return toMastery(m);
}

export async function getMastery(vocabId: number): Promise<MasteryState> {
  const m = await apiFetch<ApiMastery>(`/api/vocab/${vocabId}/mastery`);
  return toMastery(m);
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

interface ApiSentenceLink {
  id: number;
  vocab_id: number;
  surface_token: string;
  position: number;
  role: SentenceLinkRole;
}

interface ApiSentence {
  id: number;
  workspace_id: number;
  text: string;
  translation: string | null;
  language: LanguageCode;
  source: SentenceSource;
  source_meta: Record<string, unknown> | null;
  score: number | null;
  created_at: string;
  links: ApiSentenceLink[];
}

function toSentenceLink(link: ApiSentenceLink): SentenceLink {
  return {
    id: link.id,
    vocabId: link.vocab_id,
    surfaceToken: link.surface_token,
    position: link.position,
    role: link.role,
  };
}

function toSentenceRecord(item: ApiSentence): SentenceRecord {
  return {
    id: item.id,
    workspaceId: item.workspace_id,
    text: item.text,
    translation: item.translation,
    language: item.language,
    source: item.source,
    sourceMeta: item.source_meta,
    score: item.score,
    createdAt: Date.parse(item.created_at),
    links: item.links.map(toSentenceLink),
  };
}

export interface CreateSentenceInput {
  workspaceId: number;
  text: string;
  translation?: string | null;
  language: LanguageCode;
  source?: SentenceSource;
  sourceMeta?: Record<string, unknown> | null;
  score?: number | null;
  links?: {
    vocabId: number;
    surfaceToken: string;
    position: number;
    role?: SentenceLinkRole;
  }[];
}

export async function createSentence(
  input: CreateSentenceInput,
): Promise<SentenceRecord> {
  const item = await apiFetch<ApiSentence>("/api/sentences", {
    method: "POST",
    body: JSON.stringify({
      workspace_id: input.workspaceId,
      text: input.text,
      translation: input.translation ?? null,
      language: input.language,
      source: input.source ?? "manual",
      source_meta: input.sourceMeta ?? null,
      score: input.score ?? null,
      links: (input.links ?? []).map((link) => ({
        vocab_id: link.vocabId,
        surface_token: link.surfaceToken,
        position: link.position,
        role: link.role ?? "context",
      })),
    }),
  });
  return toSentenceRecord(item);
}

export async function listSentences(params: {
  workspaceId: number;
  vocabId?: number;
  limit?: number;
}): Promise<SentenceRecord[]> {
  const search = new URLSearchParams({
    workspace_id: String(params.workspaceId),
  });
  if (params.vocabId !== undefined) search.set("vocab_id", String(params.vocabId));
  if (params.limit !== undefined) search.set("limit", String(params.limit));
  const res = await apiFetch<{ items: ApiSentence[] }>(
    `/api/sentences?${search.toString()}`,
  );
  return res.items.map(toSentenceRecord);
}

export async function getSentence(id: number): Promise<SentenceRecord> {
  const item = await apiFetch<ApiSentence>(`/api/sentences/${id}`);
  return toSentenceRecord(item);
}

export async function deleteSentence(id: number): Promise<void> {
  await apiFetch<{ ok: boolean }>(`/api/sentences/${id}`, { method: "DELETE" });
}

interface ApiTokenCandidate {
  vocab_id: number;
  word: string;
  lemma: string | null;
  surface_form: string | null;
  translation: string;
}

interface ApiTokenSpan {
  token: string;
  start: number;
  end: number;
  normalized: string;
  vocab_id: number | null;
  candidates: ApiTokenCandidate[];
  confidence: number | null;
}

interface ApiTokenResolveResponse {
  spans: ApiTokenSpan[];
}

export async function resolveTokens(input: {
  workspaceId: number;
  language: LanguageCode;
  text: string;
}): Promise<ApiTokenSpan[]> {
  const res = await apiFetch<ApiTokenResolveResponse>("/api/tokens/resolve", {
    method: "POST",
    body: JSON.stringify({
      workspace_id: input.workspaceId,
      language: input.language,
      text: input.text,
    }),
  });
  return res.spans;
}

export async function tokenAction(input: {
  action: "open_word" | "add_to_vocab" | "record_occurrence";
  workspaceId: number;
  language: LanguageCode;
  token: string;
  vocabId?: number;
  gloss?: string;
  contextType?: string;
  contextId?: string;
  charStart?: number;
  charEnd?: number;
  source?: string;
  meta?: Record<string, unknown>;
}): Promise<{ ok: boolean; destination?: string; occurrence_id?: number; vocab?: VocabItem }> {
  const res = await apiFetch<{
    ok: boolean;
    destination: string | null;
    occurrence_id: number | null;
    vocab: ApiVocab | null;
  }>("/api/tokens/action", {
    method: "POST",
    body: JSON.stringify({
      action: input.action,
      workspace_id: input.workspaceId,
      language: input.language,
      token: input.token,
      vocab_id: input.vocabId ?? null,
      gloss: input.gloss ?? null,
      context_type: input.contextType ?? "manual",
      context_id: input.contextId ?? null,
      char_start: input.charStart ?? null,
      char_end: input.charEnd ?? null,
      source: input.source ?? "manual",
      meta: input.meta ?? null,
    }),
  });
  return {
    ok: res.ok,
    destination: res.destination ?? undefined,
    occurrence_id: res.occurrence_id ?? undefined,
    vocab: res.vocab ? toVocab(res.vocab, input.language) : undefined,
  };
}
