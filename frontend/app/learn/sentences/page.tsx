"use client";

import {
  Check,
  ChevronLeft,
  ChevronRight,
  HelpCircle,
  Loader2,
  Mic,
  MicOff,
  RefreshCw,
  RotateCcw,
  SkipForward,
  Volume2,
  X,
} from "lucide-react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import {
  Suspense,
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";
import { SelectionCapture } from "@/components/SelectionCapture";
import { SettingsPopover } from "@/components/SettingsPopover";
import { TokenizedText } from "@/components/TokenizedText";
import { createSentence, generateOrMock } from "@/lib/api";
import { cn } from "@/lib/cn";
import { usePracticeSettings, useVocab } from "@/lib/storage";
import { playTTS, useVoiceCapture } from "@/lib/voice";
import type {
  PracticeSettings,
  SentenceCandidate,
  VocabItem,
} from "@/lib/types";

function normalize(s: string) {
  return s
    .trim()
    .toLowerCase()
    .replace(/[.,!?¿¡;:"']/g, "")
    .replace(/\s+/g, " ");
}

interface PromptPair {
  prompt: string;
  expected: string;
  promptLanguage: "en" | "es";
}

function pickPromptPair(
  candidate: SentenceCandidate | null,
  direction: PracticeSettings["direction"],
): PromptPair | null {
  if (!candidate || !candidate.translation) return null;
  if (direction === "en-to-es") {
    return {
      prompt: candidate.translation,
      expected: candidate.sentence,
      promptLanguage: "en",
    };
  }
  return {
    prompt: candidate.sentence,
    expected: candidate.translation,
    promptLanguage: "es",
  };
}

interface ClozeQuestion {
  sentenceWithBlank: string;
  options: { id: number; word: string; translation: string }[];
  correctId: number;
}

function buildCloze(
  candidate: SentenceCandidate | null,
  current: VocabItem,
  pool: VocabItem[],
): ClozeQuestion | null {
  if (!candidate) return null;
  const target = current.word;
  const escaped = target.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
  const re = new RegExp(`\\b${escaped}\\b`, "i");
  if (!re.test(candidate.sentence)) return null;
  const sentenceWithBlank = candidate.sentence.replace(re, "____");

  const sameTagPool = pool.filter(
    (v) =>
      v.id !== current.id &&
      v.word.toLowerCase() !== target.toLowerCase() &&
      v.tags.some((t) => current.tags.includes(t)),
  );
  const fallbackPool = pool.filter(
    (v) => v.id !== current.id && v.word.toLowerCase() !== target.toLowerCase(),
  );
  const distractorSource =
    sameTagPool.length >= 3 ? sameTagPool : fallbackPool;
  if (distractorSource.length < 3) return null;

  const distractors: VocabItem[] = [];
  const used = new Set<number>();
  while (distractors.length < 3 && used.size < distractorSource.length) {
    const pick =
      distractorSource[Math.floor(Math.random() * distractorSource.length)];
    if (used.has(pick.id)) continue;
    used.add(pick.id);
    distractors.push(pick);
  }

  const options = [
    { id: current.id, word: current.word, translation: current.translation },
    ...distractors.map((d) => ({
      id: d.id,
      word: d.word,
      translation: d.translation,
    })),
  ].sort(() => Math.random() - 0.5);

  return {
    sentenceWithBlank,
    options,
    correctId: current.id,
  };
}

interface SessionStats {
  correct: number;
  incorrect: number;
  skipped: number;
  hinted: number;
}

const ZERO_STATS: SessionStats = {
  correct: 0,
  incorrect: 0,
  skipped: 0,
  hinted: 0,
};

function SentencePracticeInner() {
  const { vocab, hydrated, recordOutcome, addVocab, activeWorkspace } = useVocab();
  const { settings, setSettings, hydrated: settingsHydrated } =
    usePracticeSettings();
  const searchParams = useSearchParams();
  const wordParam = searchParams.get("word");

  const filteredVocab = useMemo(() => {
    if (wordParam) {
      const wordId = Number(wordParam);
      const match = Number.isFinite(wordId)
        ? vocab.find((v) => v.id === wordId)
        : undefined;
      return match ? [match] : [];
    }
    if (settings.tagFilter.length === 0) return vocab;
    return vocab.filter((v) =>
      v.tags.some((t) => settings.tagFilter.includes(t)),
    );
  }, [vocab, wordParam, settings.tagFilter]);

  const [wordIndex, setWordIndex] = useState(0);
  const [cache, setCache] = useState<Map<number, SentenceCandidate>>(new Map());
  const [generating, setGenerating] = useState(false);
  const [isMock, setIsMock] = useState(false);
  const [constraintFellBack, setConstraintFellBack] = useState(false);
  const [savedSentenceIds, setSavedSentenceIds] = useState<Set<number>>(new Set());

  const [answer, setAnswer] = useState("");
  const [feedback, setFeedback] = useState<"correct" | "incorrect" | null>(null);
  const [hintRevealed, setHintRevealed] = useState(false);
  const [selectedOption, setSelectedOption] = useState<number | null>(null);

  const [stats, setStats] = useState<SessionStats>(ZERO_STATS);
  const [finished, setFinished] = useState(false);
  const [scoredIds, setScoredIds] = useState<Set<number>>(new Set());

  const generationToken = useRef(0);
  const advanceTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const sentenceSectionRef = useRef<HTMLElement | null>(null);

  // Voice mode plumbing (LOS voice mode). Tracks whether we've already kicked
  // off the prompt-read-then-listen sequence for the current word so the
  // effect doesn't restart mid-question.
  const voicePromptToken = useRef<number | null>(null);
  const [voiceTranscript, setVoiceTranscript] = useState("");
  const [voiceError, setVoiceError] = useState<string | null>(null);
  const modeParamApplied = useRef(false);

  // Invalidate cache + reset session whenever generation constraints change.
  useEffect(() => {
    setCache(new Map());
    setScoredIds(new Set());
    setStats(ZERO_STATS);
    setFinished(false);
    setWordIndex(0);
    setConstraintFellBack(false);
  }, [
    settings.tense,
    settings.person,
    settings.number,
    settings.sentenceLength,
    settings.direction,
    settings.lexiconConstraint,
    settings.stretchCount,
  ]);

  // Reset position when filtered list shrinks past the cursor.
  useEffect(() => {
    if (wordIndex >= filteredVocab.length && filteredVocab.length > 0) {
      setWordIndex(0);
    }
  }, [filteredVocab.length, wordIndex]);

  // Reset session when the practice scope changes.
  useEffect(() => {
    setStats(ZERO_STATS);
    setScoredIds(new Set());
    setFinished(false);
    setWordIndex(0);
  }, [filteredVocab.length, wordParam]);

  const current = filteredVocab[wordIndex];
  const candidate = current ? cache.get(current.id) ?? null : null;

  const targetLanguage = activeWorkspace?.language ?? "es";

  // ?mode=voice in the URL pre-selects voice mode once settings are hydrated.
  // We only apply this once per page mount so the user can switch modes
  // afterwards via the settings popover without it snapping back.
  const modeParam = searchParams.get("mode");
  useEffect(() => {
    if (!settingsHydrated || modeParamApplied.current) return;
    if (modeParam === "voice" && settings.mode !== "voice") {
      setSettings({ ...settings, mode: "voice" });
    }
    modeParamApplied.current = true;
  }, [settingsHydrated, modeParam, settings, setSettings]);

  const generateFor = useCallback(
    async (word: VocabItem, force = false) => {
      if (!force && cache.has(word.id)) return;
      const myToken = ++generationToken.current;
      setGenerating(true);
      try {
        const res = await generateOrMock({
          word: word.word,
          translation: word.translation,
          tense: settings.tense,
          person: settings.person,
          number: settings.number,
          sentence_length: settings.sentenceLength,
          direction: settings.direction,
          num_candidates: 1,
          lexicon_constraint: settings.lexiconConstraint,
          workspace_id: activeWorkspace?.id,
          stretch_count: settings.stretchCount,
        });
        if (myToken !== generationToken.current) return;
        const next = res.candidates[0] ?? null;
        if (next) {
          setCache((prev) => {
            const m = new Map(prev);
            m.set(word.id, next);
            return m;
          });
          if (
            activeWorkspace &&
            !savedSentenceIds.has(word.id) &&
            next.sentence.trim().length > 0
          ) {
            const token = word.word.trim();
            const position = next.sentence
              .toLowerCase()
              .indexOf(token.toLowerCase());
            void createSentence({
              workspaceId: activeWorkspace.id,
              language: activeWorkspace.language,
              text: next.sentence,
              translation: next.translation,
              source: "generated",
              sourceMeta: {
                origin: "sentence_practice",
                vocabId: word.id,
              },
              links:
                position >= 0
                  ? [
                      {
                        vocabId: word.id,
                        surfaceToken: next.sentence.slice(position, position + token.length),
                        position,
                        role: "target",
                      },
                    ]
                  : [],
            })
              .then(() =>
                setSavedSentenceIds((prev) => {
                  const s = new Set(prev);
                  s.add(word.id);
                  return s;
                }),
              )
              .catch(() => undefined);
          }
        }
        setIsMock(Boolean(res.mock));
        // Constraint requested but server returned unconstrained results.
        const requested = settings.lexiconConstraint !== "off";
        const honored = Boolean(res.constrained);
        setConstraintFellBack(requested && !honored && !res.mock);
      } finally {
        if (myToken === generationToken.current) setGenerating(false);
      }
    },
    [
      cache,
      settings.tense,
      settings.person,
      settings.number,
      settings.sentenceLength,
      settings.direction,
      settings.lexiconConstraint,
      settings.stretchCount,
      activeWorkspace?.id,
      activeWorkspace?.language,
      savedSentenceIds,
    ],
  );

  // Reset per-card UI when the visible word changes.
  useEffect(() => {
    setAnswer("");
    setFeedback(null);
    setHintRevealed(false);
    setSelectedOption(null);
    setVoiceTranscript("");
    setVoiceError(null);
    if (advanceTimer.current) {
      clearTimeout(advanceTimer.current);
      advanceTimer.current = null;
    }
  }, [current?.id]);

  // Trigger generation for the current word if missing from cache.
  useEffect(() => {
    if (!hydrated || !settingsHydrated || !current || finished) return;
    if (!cache.has(current.id)) {
      void generateFor(current);
    }
  }, [hydrated, settingsHydrated, current, finished, cache, generateFor]);

  const pair = pickPromptPair(candidate, settings.direction);

  // ── Voice mode capture ─────────────────────────────────────────────────
  // The hook owns the WebSocket + mic stream. We pass it a callback that
  // reads the latest `pair` / settings via closure; the hook stores it in
  // a ref so we don't need to re-bind on every render.
  const voice = useVoiceCapture({
    onTranscript: (transcript) => {
      setVoiceTranscript(transcript);
      if (!pair) return;
      const ok = normalize(transcript) === normalize(pair.expected);
      setFeedback(ok ? "correct" : "incorrect");
      trackOutcome(ok ? "correct" : "incorrect");
      voice.stop();
      if (ok) {
        // Read the correct answer back for pronunciation reinforcement,
        // then optionally auto-advance.
        playTTS(pair.expected, targetLanguage)
          .catch(() => undefined)
          .finally(() => {
            if (settings.autoAdvance) {
              advanceTimer.current = setTimeout(advanceOrFinish, 600);
            }
          });
      } else {
        // Restart listening so the user can try again without tapping.
        advanceTimer.current = setTimeout(() => {
          setFeedback(null);
          setVoiceTranscript("");
          void voice.start();
        }, 1600);
      }
    },
    onError: (msg) => setVoiceError(msg),
  });

  // Voice mode: when the prompt for a new word is ready, read it aloud and
  // then start listening. We guard with a per-word token so re-renders don't
  // restart the audio mid-question.
  useEffect(() => {
    if (settings.mode !== "voice") return;
    if (!pair || !current) return;
    if (voicePromptToken.current === current.id) return;
    voicePromptToken.current = current.id;
    voice.stop();
    setVoiceTranscript("");
    setVoiceError(null);
    const promptLang = pair.promptLanguage;
    playTTS(pair.prompt, promptLang)
      .catch(() => undefined)
      .finally(() => {
        // Don't start listening if the user has switched word/mode in the
        // meantime — token check guards against that race.
        if (voicePromptToken.current !== current.id) return;
        if (settings.mode !== "voice") return;
        void voice.start();
      });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [current?.id, pair, settings.mode]);

  // Switching away from voice mode (or unmounting) tears down the mic + WS.
  useEffect(() => {
    if (settings.mode !== "voice") {
      voice.stop();
      voicePromptToken.current = null;
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [settings.mode]);

  const cloze = useMemo(() => {
    if (settings.mode !== "multiple-choice") return null;
    if (!current || !candidate) return null;
    return buildCloze(candidate, current, vocab);
  }, [settings.mode, current, candidate, vocab]);

  const advanceOrFinish = useCallback(() => {
    if (advanceTimer.current) {
      clearTimeout(advanceTimer.current);
      advanceTimer.current = null;
    }
    if (filteredVocab.length === 0) return;
    if (wordIndex >= filteredVocab.length - 1) {
      setFinished(true);
    } else {
      setWordIndex((i) => i + 1);
    }
  }, [filteredVocab.length, wordIndex]);

  function trackOutcome(
    kind: "correct" | "incorrect" | "skipped" | "hinted",
  ) {
    if (!current) return;
    if (scoredIds.has(current.id)) return;
    setScoredIds((s) => new Set(s).add(current.id));
    setStats((s) => ({ ...s, [kind]: s[kind] + 1 }));
    // Persist outcome against the canonical mastery state (LOS-901).
    void recordOutcome(current.id, kind, "sentences");
  }

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!pair) return;
    const ok = normalize(answer) === normalize(pair.expected);
    setFeedback(ok ? "correct" : "incorrect");
    trackOutcome(ok ? "correct" : "incorrect");
    if (ok) {
      advanceTimer.current = setTimeout(() => advanceOrFinish(), 1200);
    }
  }

  function handleClozeChoose(optionId: number) {
    if (!cloze || selectedOption) return;
    setSelectedOption(optionId);
    const ok = optionId === cloze.correctId;
    setFeedback(ok ? "correct" : "incorrect");
    trackOutcome(ok ? "correct" : "incorrect");
    if (ok) {
      advanceTimer.current = setTimeout(() => advanceOrFinish(), 1100);
    }
  }

  function handleSkip() {
    trackOutcome("skipped");
    advanceOrFinish();
  }

  function handleNotSure() {
    if (!hintRevealed) trackOutcome("hinted");
    setHintRevealed(true);
  }

  function handleNextWord() {
    advanceOrFinish();
  }

  function handlePrev() {
    if (filteredVocab.length === 0) return;
    if (advanceTimer.current) {
      clearTimeout(advanceTimer.current);
      advanceTimer.current = null;
    }
    setWordIndex(
      (i) => (i - 1 + filteredVocab.length) % filteredVocab.length,
    );
  }

  function handleRestart() {
    setStats(ZERO_STATS);
    setScoredIds(new Set());
    setFinished(false);
    setWordIndex(0);
  }

  function handleRegenerate() {
    if (!current) return;
    setCache((prev) => {
      const m = new Map(prev);
      m.delete(current.id);
      return m;
    });
    setFeedback(null);
    setSelectedOption(null);
    setHintRevealed(false);
    setAnswer("");
    void generateFor(current, true);
  }

  return (
    <div className="space-y-6">
      <SelectionCapture
        containerRef={sentenceSectionRef}
        onAddWord={async (surfaceForm) => {
          const item = await addVocab({ surfaceForm });
          return item.surfaceForm ?? item.word;
        }}
      />
      <div className="flex items-start justify-between gap-4">
        <header>
          <h1 className="text-3xl font-bold text-slate-900">Sentence Practice</h1>
          <p className="text-slate-500 mt-1">
            Practice words in context with generated sentence drills.
          </p>
        </header>
        <div className="flex items-center gap-2">
          {settings.mode === "voice" && (
            <button
              type="button"
              onClick={() =>
                setSettings({ ...settings, autoAdvance: !settings.autoAdvance })
              }
              className={cn(
                "inline-flex items-center gap-1.5 rounded-2xl px-4 py-3 text-xs font-bold tracking-wider transition shadow-soft",
                settings.autoAdvance
                  ? "bg-emerald-500 text-white"
                  : "bg-white/70 text-slate-500 border border-slate-200",
              )}
              title="Auto-advance to the next sentence after a correct answer"
            >
              AUTO {settings.autoAdvance ? "ON" : "OFF"}
            </button>
          )}
          <SettingsPopover settings={settings} onChange={setSettings} />
        </div>
      </div>

      {wordParam && filteredVocab.length > 0 && (
        <div className="rounded-xl bg-blue-50 border border-blue-100 px-4 py-2 text-sm text-blue-700">
          Practicing a single word.{" "}
          <Link href="/learn/sentences" className="underline">
            Switch to full deck
          </Link>
          .
        </div>
      )}

      {!hydrated || !settingsHydrated ? (
        <div className="glass-card rounded-2xl p-12 text-center text-slate-400">
          Loading…
        </div>
      ) : vocab.length === 0 ? (
        <div className="glass-card rounded-2xl p-12 text-center">
          <p className="text-slate-600">
            Add some words on the{" "}
            <Link href="/words" className="text-brand-600 underline">
              Words page
            </Link>{" "}
            first.
          </p>
        </div>
      ) : filteredVocab.length === 0 ? (
        <div className="glass-card rounded-2xl p-12 text-center">
          <p className="text-slate-600">
            {wordParam
              ? "That word isn't in your collection. "
              : "No words match the current tag filter. Adjust it from "}
            <span className="font-medium">Settings</span>.
          </p>
        </div>
      ) : finished ? (
        <SessionSummary
          stats={stats}
          total={filteredVocab.length}
          onRestart={handleRestart}
        />
      ) : (
        <>
          <section className="glass-card rounded-2xl p-4 flex items-center justify-between gap-4">
            <button
              type="button"
              onClick={handlePrev}
              disabled={filteredVocab.length <= 1}
              className="h-10 w-10 rounded-xl bg-slate-100 text-slate-700 flex items-center justify-center hover:bg-slate-200 disabled:opacity-40 disabled:cursor-not-allowed transition"
              aria-label="Previous word"
            >
              <ChevronLeft className="h-5 w-5" strokeWidth={2.5} />
            </button>

            <div className="flex-1 text-center">
              <div className="text-xs uppercase tracking-wide text-slate-500">
                Practicing word {wordIndex + 1} of {filteredVocab.length}
              </div>
              <div className="text-2xl font-bold text-slate-900 mt-0.5">
                {current?.word}
              </div>
              <div className="text-sm text-slate-500">
                {current?.translation}
              </div>
            </div>

            <button
              type="button"
              onClick={handleNextWord}
              disabled={filteredVocab.length <= 1}
              className="h-10 w-10 rounded-xl bg-slate-100 text-slate-700 flex items-center justify-center hover:bg-slate-200 disabled:opacity-40 disabled:cursor-not-allowed transition"
              aria-label="Next word"
            >
              <ChevronRight className="h-5 w-5" strokeWidth={2.5} />
            </button>
          </section>

          <section
            ref={sentenceSectionRef}
            className="rounded-3xl bg-gradient-to-br from-white via-white to-slate-50 shadow-card p-12 min-h-[280px] relative flex flex-col items-center justify-center"
          >
            {isMock && (
              <div className="absolute top-4 right-4 px-3 py-1 rounded-full bg-amber-100 text-amber-700 text-xs font-medium">
                Demo mode
              </div>
            )}
            {!isMock && constraintFellBack && (
              <div
                className="absolute top-4 right-4 px-3 py-1 rounded-full bg-amber-50 text-amber-700 text-xs font-medium border border-amber-200"
                title="No candidates fit the lexicon constraint, so an unconstrained sentence was used."
              >
                Constraint relaxed
              </div>
            )}
            <button
              type="button"
              onClick={handleRegenerate}
              disabled={generating || !candidate}
              title="Generate a different sentence"
              aria-label="Regenerate sentence"
              className="absolute top-5 left-5 h-10 w-10 rounded-xl bg-slate-100 text-slate-600 flex items-center justify-center hover:bg-slate-200 disabled:opacity-40 disabled:cursor-not-allowed transition"
            >
              <RefreshCw
                className={cn("h-5 w-5", generating && "animate-spin")}
                strokeWidth={2}
              />
            </button>
            <button
              type="button"
              onClick={handleNotSure}
              className="absolute top-5 right-5 h-10 w-10 rounded-xl bg-slate-900 text-white flex items-center justify-center hover:bg-slate-800 transition"
              aria-label="Show hint"
              title="Reveal expected answer"
            >
              <HelpCircle className="h-5 w-5" strokeWidth={2} />
            </button>

            {generating && !candidate ? (
              <div className="flex items-center gap-2 text-slate-500">
                <Loader2 className="h-5 w-5 animate-spin" />
                Generating sentence…
              </div>
            ) : settings.mode === "multiple-choice" && cloze ? (
              <>
                <div className="text-slate-500">Fill in the blank:</div>
                <div className="mt-3 text-2xl md:text-3xl font-bold text-slate-900 text-center">
                  <TokenizedText
                    text={cloze.sentenceWithBlank}
                    language={activeWorkspace?.language ?? "es"}
                    sourceContext={{
                      type: "sentence_practice_cloze",
                      id: current?.id,
                    }}
                  />
                </div>
                {candidate?.translation && (
                  <div className="mt-3 text-sm text-slate-500 italic">
                    {candidate.translation}
                  </div>
                )}
              </>
            ) : pair ? (
              <>
                <div className="text-slate-500">Translate this sentence:</div>
                <div className="mt-3 text-3xl md:text-4xl font-bold text-slate-900 text-center">
                  {pair.promptLanguage === "es" ? (
                    <TokenizedText
                      text={pair.prompt}
                      language={activeWorkspace?.language ?? "es"}
                      sourceContext={{
                        type: "sentence_practice_prompt",
                        id: current?.id,
                      }}
                    />
                  ) : (
                    pair.prompt
                  )}
                </div>
                {hintRevealed && (
                  <div className="mt-6 text-sm text-slate-500">
                    Expected:{" "}
                    <span className="font-medium text-slate-700">
                      {pair.promptLanguage === "en" ? (
                        <TokenizedText
                          text={pair.expected}
                          language={activeWorkspace?.language ?? "es"}
                          sourceContext={{
                            type: "sentence_practice_expected",
                            id: current?.id,
                          }}
                        />
                      ) : (
                        pair.expected
                      )}
                    </span>
                  </div>
                )}
              </>
            ) : (
              <div className="text-slate-500 text-sm text-center max-w-sm">
                Couldn&apos;t generate a sentence. Check that the backend is
                running and{" "}
                <code className="rounded bg-slate-100 px-1.5 py-0.5 text-xs text-slate-700">
                  OPENAI_API_KEY
                </code>{" "}
                is set, or use the seed words for demo mode.
              </div>
            )}
          </section>

          <div className="flex items-center justify-center gap-6 text-sm text-slate-600">
            <button
              type="button"
              onClick={handleNotSure}
              disabled={!pair && !cloze}
              className="inline-flex items-center gap-1.5 hover:text-slate-900 disabled:opacity-50 disabled:cursor-not-allowed transition"
            >
              <HelpCircle className="h-4 w-4" strokeWidth={2} />
              Not sure
            </button>
            <button
              type="button"
              onClick={handleSkip}
              className="inline-flex items-center gap-1.5 hover:text-slate-900 transition"
            >
              <SkipForward className="h-4 w-4" strokeWidth={2} />
              Skip
            </button>
            <button
              type="button"
              onClick={handleNextWord}
              className="inline-flex items-center gap-1.5 hover:text-slate-900 transition"
            >
              Next word
              <ChevronRight className="h-4 w-4" strokeWidth={2} />
            </button>
          </div>

          {settings.mode === "multiple-choice" && cloze ? (
            <div className="glass-card rounded-2xl p-6 space-y-3">
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                {cloze.options.map((opt) => {
                  const isSelected = selectedOption === opt.id;
                  const isCorrect = opt.id === cloze.correctId;
                  const showState = selectedOption !== null;
                  return (
                    <button
                      key={opt.id}
                      type="button"
                      onClick={() => handleClozeChoose(opt.id)}
                      disabled={selectedOption !== null}
                      className={cn(
                        "rounded-xl border px-4 py-3 text-left transition",
                        !showState &&
                          "border-slate-200 bg-white hover:bg-slate-50",
                        showState &&
                          isCorrect &&
                          "border-emerald-300 bg-emerald-50",
                        showState &&
                          !isCorrect &&
                          isSelected &&
                          "border-rose-300 bg-rose-50",
                        showState &&
                          !isCorrect &&
                          !isSelected &&
                          "border-slate-200 bg-white opacity-60",
                      )}
                    >
                      <div className="font-semibold text-slate-900">
                        {opt.word}
                      </div>
                      <div className="text-xs text-slate-500">
                        {opt.translation}
                      </div>
                    </button>
                  );
                })}
              </div>
              {feedback && (
                <div
                  className={cn(
                    "rounded-xl p-3 text-sm",
                    feedback === "correct"
                      ? "bg-emerald-50 text-emerald-700"
                      : "bg-rose-50 text-rose-700",
                  )}
                >
                  {feedback === "correct" ? (
                    <span>¡Correcto! Advancing…</span>
                  ) : (
                    <span>
                      Not quite. Correct word: <strong>{current?.word}</strong>
                    </span>
                  )}
                </div>
              )}
            </div>
          ) : settings.mode === "multiple-choice" && pair ? (
            <div className="rounded-2xl bg-amber-50 border border-amber-100 p-4 text-sm text-amber-700">
              Multiple-choice mode needs a sentence that includes the target
              word. Falling back to typing for this card — or try{" "}
              <button
                type="button"
                onClick={handleRegenerate}
                className="underline font-medium"
              >
                regenerating
              </button>
              .
            </div>
          ) : null}

          {settings.mode === "voice" && pair && (
            <VoiceCard
              expected={pair.expected}
              promptLanguage={pair.promptLanguage}
              targetLanguage={targetLanguage}
              promptText={pair.prompt}
              voiceState={voice.state}
              level={voice.level}
              transcript={voiceTranscript}
              error={voiceError}
              feedback={feedback}
              onReplayPrompt={() =>
                playTTS(pair.prompt, pair.promptLanguage).catch(() => undefined)
              }
              onTryAgain={() => {
                setFeedback(null);
                setVoiceTranscript("");
                setVoiceError(null);
                void voice.start();
              }}
            />
          )}

          {(settings.mode === "typing" ||
            (settings.mode === "multiple-choice" && !cloze && pair)) && (
            <form
              onSubmit={handleSubmit}
              className="glass-card rounded-2xl p-6 flex flex-col gap-4"
            >
              <input
                value={answer}
                onChange={(e) => {
                  setAnswer(e.target.value);
                  setFeedback(null);
                }}
                placeholder="Type your answer..."
                disabled={!pair || generating}
                className="w-full rounded-xl border border-slate-200 bg-white px-4 py-3 text-slate-900 placeholder:text-slate-400 focus:outline-none focus:ring-2 focus:ring-brand-400 disabled:bg-slate-50"
              />
              <div className="flex items-center justify-center">
                <button
                  type="submit"
                  disabled={!answer.trim() || !pair || generating}
                  className={cn(
                    "rounded-xl px-8 py-2.5 font-medium text-white transition",
                    answer.trim() && pair && !generating
                      ? "bg-btn-purple hover:brightness-110 shadow-card"
                      : "bg-slate-300 cursor-not-allowed",
                  )}
                >
                  Submit
                </button>
              </div>
              {feedback && pair && (
                <div
                  className={cn(
                    "rounded-xl p-4 text-sm",
                    feedback === "correct"
                      ? "bg-emerald-50 text-emerald-700"
                      : "bg-rose-50 text-rose-700",
                  )}
                >
                  {feedback === "correct" ? (
                    <span>¡Correcto! Advancing…</span>
                  ) : (
                    <span>
                      Not quite. Expected:{" "}
                      <strong>{pair.expected}</strong>
                    </span>
                  )}
                </div>
              )}
            </form>
          )}
        </>
      )}
    </div>
  );
}

function SessionSummary({
  stats,
  total,
  onRestart,
}: {
  stats: SessionStats;
  total: number;
  onRestart: () => void;
}) {
  const answered = stats.correct + stats.incorrect;
  const accuracy =
    answered > 0 ? Math.round((stats.correct / answered) * 100) : 0;
  return (
    <div className="rounded-3xl bg-white/90 backdrop-blur shadow-card p-10 text-center space-y-6">
      <div>
        <div className="text-4xl">🎉</div>
        <h2 className="text-2xl font-bold text-slate-900 mt-2">
          Session complete
        </h2>
        <p className="text-slate-500 mt-1">
          {total} word{total === 1 ? "" : "s"} reviewed
        </p>
      </div>
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 max-w-xl mx-auto">
        <SummaryStat label="Correct" value={stats.correct} accent="emerald" />
        <SummaryStat label="Incorrect" value={stats.incorrect} accent="rose" />
        <SummaryStat label="Skipped" value={stats.skipped} accent="slate" />
        <SummaryStat label="Hinted" value={stats.hinted} accent="amber" />
      </div>
      <div className="text-sm text-slate-500">
        Accuracy on answered:{" "}
        <span className="font-semibold text-slate-700">{accuracy}%</span>
      </div>
      <button
        type="button"
        onClick={onRestart}
        className="inline-flex items-center gap-2 px-5 py-2.5 rounded-xl bg-btn-purple text-white font-medium shadow-soft hover:brightness-110 transition"
      >
        <RotateCcw className="h-4 w-4" strokeWidth={2.5} />
        Start over
      </button>
    </div>
  );
}

function SummaryStat({
  label,
  value,
  accent,
}: {
  label: string;
  value: number;
  accent: "emerald" | "rose" | "slate" | "amber";
}) {
  const palette: Record<typeof accent, { bg: string; text: string; sub: string }> = {
    emerald: { bg: "bg-emerald-50", text: "text-emerald-600", sub: "text-emerald-700" },
    rose: { bg: "bg-rose-50", text: "text-rose-600", sub: "text-rose-700" },
    slate: { bg: "bg-slate-50", text: "text-slate-700", sub: "text-slate-500" },
    amber: { bg: "bg-amber-50", text: "text-amber-600", sub: "text-amber-700" },
  };
  const p = palette[accent];
  return (
    <div className={cn("rounded-2xl p-4", p.bg)}>
      <div className={cn("text-2xl font-bold", p.text)}>{value}</div>
      <div className={cn("text-xs mt-0.5", p.sub)}>{label}</div>
    </div>
  );
}

/** Five animated bars that visualise mic activity. Heights respond to the
 *  live RMS amplitude (`level`, 0-1) so the waveform reads as the user's
 *  actual voice rather than just a canned animation. */
function WaveformBars({ active, level }: { active: boolean; level: number }) {
  // Bar heights are a blend of the staggered base animation (CSS) and the
  // live RMS level so silence collapses the bars and louder speech expands
  // them. Each bar gets a different multiplier for a wave-like envelope.
  const multipliers = [0.6, 0.85, 1, 0.85, 0.6];
  const animClasses = [
    "animate-wave-1",
    "animate-wave-2",
    "animate-wave-3",
    "animate-wave-4",
    "animate-wave-5",
  ];
  return (
    <div className="flex items-center gap-1.5 h-16">
      {multipliers.map((mult, i) => {
        if (!active) {
          return (
            <div
              key={i}
              className="w-2.5 h-3 rounded-full bg-slate-300"
            />
          );
        }
        const liveScale = Math.max(0.18, Math.min(1, level * mult * 1.6));
        return (
          <div
            key={i}
            className={cn(
              "w-2.5 rounded-full bg-emerald-500 origin-center",
              animClasses[i],
            )}
            style={{
              height: `${Math.round(20 + liveScale * 44)}px`,
            }}
          />
        );
      })}
    </div>
  );
}

interface VoiceCardProps {
  expected: string;
  promptText: string;
  promptLanguage: "en" | "es";
  targetLanguage: string;
  voiceState: "idle" | "connecting" | "listening" | "processing" | "error";
  level: number;
  transcript: string;
  error: string | null;
  feedback: "correct" | "incorrect" | null;
  onReplayPrompt: () => void;
  onTryAgain: () => void;
}

function VoiceCard({
  expected,
  promptText,
  voiceState,
  level,
  transcript,
  error,
  feedback,
  onReplayPrompt,
  onTryAgain,
}: VoiceCardProps) {
  const isListening = voiceState === "listening";
  const isCorrect = feedback === "correct";
  const isIncorrect = feedback === "incorrect";

  return (
    <div className="glass-card rounded-2xl p-6 flex flex-col items-center gap-5">
      {/* Status header */}
      <div className="w-full flex items-center justify-between">
        <button
          type="button"
          onClick={onReplayPrompt}
          className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-xl bg-slate-100 text-slate-600 text-xs font-medium hover:bg-slate-200 transition"
          title="Replay prompt"
        >
          <Volume2 className="h-4 w-4" strokeWidth={2} />
          Replay
        </button>
        <div className="text-xs uppercase tracking-wide text-slate-400">
          {voiceState === "connecting" && "Connecting…"}
          {voiceState === "listening" && "Listening"}
          {voiceState === "processing" && "Transcribing…"}
          {voiceState === "idle" && !feedback && "Ready"}
          {voiceState === "error" && "Mic unavailable"}
        </div>
      </div>

      {/* Waveform visualization */}
      <div className="flex flex-col items-center gap-2 py-3">
        <WaveformBars active={isListening} level={level} />
        <div className="text-sm text-slate-500 italic min-h-[1.5rem]">
          {voiceState === "connecting" && "Opening microphone…"}
          {voiceState === "listening" && (transcript || "Speak now…")}
          {voiceState === "processing" && (transcript || "One sec…")}
          {voiceState === "idle" && !feedback && "Tap Try again to start"}
          {voiceState === "error" && (error ?? "Microphone error")}
        </div>
      </div>

      {/* Feedback */}
      {isCorrect && (
        <div className="w-full flex flex-col items-center gap-2 rounded-xl bg-emerald-50 border border-emerald-200 p-4">
          <div className="h-10 w-10 rounded-full bg-emerald-500 flex items-center justify-center">
            <Check className="h-6 w-6 text-white" strokeWidth={3} />
          </div>
          <div className="text-2xl font-bold text-emerald-700 text-center">
            {expected}
          </div>
          <div className="text-xs text-emerald-600">¡Correcto!</div>
        </div>
      )}

      {isIncorrect && (
        <div className="w-full flex flex-col items-center gap-2 rounded-xl bg-rose-50 border border-rose-200 p-4">
          <div className="h-10 w-10 rounded-full bg-rose-500 flex items-center justify-center">
            <X className="h-6 w-6 text-white" strokeWidth={3} />
          </div>
          <div className="text-sm text-rose-700">
            Heard:{" "}
            <span className="font-semibold">
              {transcript || "—"}
            </span>
          </div>
          <div className="text-sm text-rose-700">
            Expected:{" "}
            <span className="font-semibold">{expected}</span>
          </div>
        </div>
      )}

      {/* Manual controls */}
      <div className="flex items-center gap-3">
        {voiceState === "error" || voiceState === "idle" ? (
          <button
            type="button"
            onClick={onTryAgain}
            className="inline-flex items-center gap-2 px-5 py-2.5 rounded-xl bg-emerald-500 text-white font-medium shadow-soft hover:bg-emerald-600 transition"
          >
            <Mic className="h-4 w-4" strokeWidth={2.5} />
            {feedback ? "Try again" : "Start listening"}
          </button>
        ) : isIncorrect ? (
          <button
            type="button"
            onClick={onTryAgain}
            className="inline-flex items-center gap-2 px-5 py-2.5 rounded-xl bg-emerald-500 text-white font-medium shadow-soft hover:bg-emerald-600 transition"
          >
            <Mic className="h-4 w-4" strokeWidth={2.5} />
            Try again
          </button>
        ) : (
          <div className="inline-flex items-center gap-1.5 text-xs text-slate-400">
            <MicOff className="h-3.5 w-3.5" strokeWidth={2} />
            Mic active — speak when ready
          </div>
        )}
      </div>

      {/* Hidden prompt text for screen readers; the card relies on TTS for sighted users */}
      <span className="sr-only">Prompt: {promptText}</span>
    </div>
  );
}

export default function SentencePracticePage() {
  return (
    <Suspense
      fallback={
        <div className="text-slate-400 text-center py-12">Loading…</div>
      }
    >
      <SentencePracticeInner />
    </Suspense>
  );
}
