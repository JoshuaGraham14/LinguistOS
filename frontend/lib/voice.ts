"use client";

/**
 * Voice mode primitives for sentence practice.
 *
 * This module is the single source of truth for everything microphone- and
 * audio-related in the practice flow:
 *
 *   prefetchTTS / playTTS / stopAllTTS — text-to-speech for prompts and
 *     correct-answer readback. Uses a shared HTMLAudioElement pool so the
 *     network round-trip overlaps with React rendering and playback feels
 *     instant.
 *
 *   playCorrectSound — locally-synthesised C-E-G chime for "you got it"
 *     feedback. No HTTP, no asset, ~360ms total.
 *
 *   useVoiceCapture — React hook that opens a WebSocket to the backend
 *     Deepgram proxy, captures microphone audio via an AudioWorklet (PCM16
 *     @ 24 kHz, sent as raw binary frames), and surfaces transcription
 *     events plus a live amplitude level for the waveform UI. Pinned to a
 *     single language and biased toward the expected sentence (via
 *     keyterm boosting on the server) so the model's acoustic decoder
 *     doesn't drift.
 */

import { useCallback, useEffect, useRef, useState } from "react";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
const TTS_BASE = `${API_URL}/api/tts`;

// ---------------------------------------------------------------------------
// TTS — prefetch + play
// ---------------------------------------------------------------------------
//
// React paints AFTER `useEffect` fires. If we waited for the effect to start
// the TTS HTTP request, the user would see the sentence on screen for ~600ms
// of dead silence. The fix is `prefetchTTS`, called the instant a candidate
// sentence arrives (synchronously, before `setCache`). The browser starts
// fetching while React is still rendering, and `playTTS` reuses the same
// Audio element — the network and render run in parallel.

function ttsUrl(text: string, language: string): string {
  const params = new URLSearchParams({ text, language });
  return `${TTS_BASE}?${params.toString()}`;
}

/** key → in-flight HTMLAudioElement that's already loading from the backend. */
const prefetchMap = new Map<string, HTMLAudioElement>();

/** The Audio element currently playing (or about to play) from playTTS.
 *  We keep one slot so a new playTTS can hard-stop the previous audio
 *  instead of letting them overlap (which sounded like garbled speech). */
let currentTTSAudio: HTMLAudioElement | null = null;

function makePrefetchAudio(url: string): HTMLAudioElement {
  const audio = new Audio(url);
  audio.preload = "auto";
  return audio;
}

/** Halt whatever TTS audio (if any) is currently playing. Idempotent. */
export function stopAllTTS(): void {
  if (currentTTSAudio) {
    try {
      currentTTSAudio.onended = null;
      currentTTSAudio.onerror = null;
      currentTTSAudio.pause();
      // Releasing the src tells the browser to abort any in-flight fetch.
      currentTTSAudio.removeAttribute("src");
      currentTTSAudio.load();
    } catch {
      /* best-effort */
    }
    currentTTSAudio = null;
  }
}

/**
 * Start loading `(text, language)` now. Call this as early as possible (e.g.
 * the moment a generated sentence lands, before React re-renders). `playTTS`
 * will find this element in `prefetchMap` and call `.play()` on it, so the
 * OpenAI round-trip overlaps with React rendering instead of following it.
 */
export function prefetchTTS(text: string, language: string): void {
  const t = text.trim();
  if (!t) return;
  const key = `${language}|${t}`;
  if (prefetchMap.has(key)) return; // already warming
  prefetchMap.set(key, makePrefetchAudio(ttsUrl(t, language)));
}

/**
 * Play `(text, language)`. If `prefetchTTS` was called earlier for the same
 * pair, the Audio element is already loading — we call `.play()` directly and
 * the browser starts as soon as it has enough buffered (much sooner than
 * starting a fresh fetch here). Resolves when playback finishes.
 *
 * Hard-stops any previously-playing TTS first so two audios never overlap.
 */
export async function playTTS(text: string, language: string): Promise<void> {
  const t = text.trim();
  if (!t) return;
  const key = `${language}|${t}`;

  stopAllTTS();

  const prefetched = prefetchMap.get(key);
  prefetchMap.delete(key);
  const audio = prefetched ?? makePrefetchAudio(ttsUrl(t, language));
  currentTTSAudio = audio;

  await new Promise<void>((resolve, reject) => {
    const cleanup = () => {
      if (currentTTSAudio === audio) currentTTSAudio = null;
    };
    audio.onended = () => {
      cleanup();
      resolve();
    };
    audio.onerror = () => {
      cleanup();
      reject(new Error("audio playback failed"));
    };
    void audio.play().catch((err) => {
      cleanup();
      reject(err);
    });
  });
}

// ---------------------------------------------------------------------------
// "Correct answer" chime — synthesised on-device, no asset.
// ---------------------------------------------------------------------------

/** Plays a short pleasant C-E-G arpeggio (~360 ms) for correct answers. */
export function playCorrectSound(): void {
  try {
    const Ctx =
      window.AudioContext ||
      (window as unknown as { webkitAudioContext: typeof AudioContext })
        .webkitAudioContext;
    if (!Ctx) return;
    const ctx = new Ctx();
    const now = ctx.currentTime;

    // C5 → E5 → G5 — ascending major triad. Reads as upbeat / success.
    const notes = [
      { freq: 523.25, start: 0.0, dur: 0.12 },
      { freq: 659.25, start: 0.08, dur: 0.12 },
      { freq: 783.99, start: 0.16, dur: 0.22 },
    ];

    for (const n of notes) {
      const osc = ctx.createOscillator();
      const gain = ctx.createGain();
      osc.type = "sine";
      osc.frequency.setValueAtTime(n.freq, now + n.start);
      osc.connect(gain);
      gain.connect(ctx.destination);
      gain.gain.setValueAtTime(0, now + n.start);
      gain.gain.linearRampToValueAtTime(0.14, now + n.start + 0.01);
      gain.gain.exponentialRampToValueAtTime(0.001, now + n.start + n.dur);
      osc.start(now + n.start);
      osc.stop(now + n.start + n.dur + 0.02);
    }

    setTimeout(() => {
      ctx.close().catch(() => undefined);
    }, 700);
  } catch {
    // best-effort; never throw from a sound effect
  }
}

// ---------------------------------------------------------------------------
// Mic capture + Deepgram WebSocket (via backend proxy)
// ---------------------------------------------------------------------------

const SAMPLE_RATE = 24000;
const NO_SPEECH_TIMEOUT_MS = 12000;
const PCM_WORKLET_URL = "/voice/pcm16-worklet.js";

export type VoiceState =
  | "idle" //          mic off, ready to start
  | "connecting" //    WS handshake / mic permission / worklet load in flight
  | "listening" //     mic open, waiting for or recording user speech
  | "processing" //    speech ended, awaiting final transcript from server
  | "error"; //        terminal error; user must hit "try again"

export type VoiceErrorKind =
  | "mic_denied"
  | "mic_unavailable"
  | "no_speech"
  | "transcription_failed"
  | "connection";

export interface VoiceCaptureCallbacks {
  /** Final transcript for one utterance. Fired once per user turn. */
  onTranscript: (transcript: string) => void;
  /** Optional: any low-level error. `kind` lets the UI tailor the message. */
  onError?: (message: string, kind: VoiceErrorKind) => void;
}

export interface VoiceStartOptions {
  /** ISO-639-1 code to lock transcription to (e.g. "es"). */
  language?: string;
  /** The canonical sentence the learner is trying to produce. Sent to the
   *  backend so it can split into Deepgram `keyterm=` query parameters,
   *  which bias the acoustic decoder toward the expected phonemes and
   *  make catastrophic mistranscriptions far less likely. */
  expected?: string;
}

// ---- Server event shapes (proxy → frontend) -------------------------------
//
// The backend speaks Deepgram upstream but exposes a stable, neutral event
// protocol to us — keyed by `type` so the message handler can switch
// exhaustively without sprinkling `any`. If you change one of these event
// shapes, change the matching `client_ws.send_json(...)` call in
// `backend/app/api/voice.py` too.

interface ServerSpeechStarted {
  type: "speech_started";
}
interface ServerSpeechStopped {
  type: "speech_stopped";
}
interface ServerTranscriptInterim {
  type: "transcript_interim";
  /** Latest snapshot of the interim transcript — REPLACES prior interim
   *  text (Deepgram emits the full running guess each frame, not deltas). */
  text: string;
}
interface ServerTranscriptFinal {
  type: "transcript_final";
  text: string;
}
interface ServerError {
  type: "error";
  message?: string;
}
interface ServerOther {
  type: string;
  [k: string]: unknown;
}

type VoiceServerEvent =
  | ServerSpeechStarted
  | ServerSpeechStopped
  | ServerTranscriptInterim
  | ServerTranscriptFinal
  | ServerError
  | ServerOther;

// ---- helpers --------------------------------------------------------------

function buildWsUrl(opts: VoiceStartOptions | undefined): string {
  const params = new URLSearchParams();
  if (opts?.language) params.set("language", opts.language);
  if (opts?.expected) params.set("expected", opts.expected);
  const qs = params.toString();
  return (
    API_URL.replace(/^http/, "ws").replace(/\/$/, "") +
    "/ws/realtime" +
    (qs ? `?${qs}` : "")
  );
}

function classifyMicError(err: unknown): {
  message: string;
  kind: VoiceErrorKind;
} {
  if (err instanceof DOMException) {
    if (err.name === "NotAllowedError" || err.name === "SecurityError") {
      return {
        kind: "mic_denied",
        message: "Microphone permission was denied. Enable it in your browser settings and try again.",
      };
    }
    if (err.name === "NotFoundError" || err.name === "OverconstrainedError") {
      return {
        kind: "mic_unavailable",
        message: "No microphone available on this device.",
      };
    }
  }
  return {
    kind: "mic_unavailable",
    message:
      err instanceof Error ? err.message : "Could not access microphone.",
  };
}

// ---- the hook -------------------------------------------------------------

export function useVoiceCapture(callbacks: VoiceCaptureCallbacks) {
  const [state, setState] = useState<VoiceState>("idle");
  const [level, setLevel] = useState(0);
  const [interim, setInterim] = useState("");
  // True between `speech_started` and `speech_stopped` from Deepgram's VAD.
  const [speaking, setSpeaking] = useState(false);

  // Latest callbacks via ref so we don't have to put them in `start`'s deps
  // (which would re-create the callback on every parent render).
  const cbRef = useRef(callbacks);
  cbRef.current = callbacks;

  // All long-lived resources we need to tear down. A single object keeps
  // them together so `stop()` is a one-liner — no chance of leaking one of
  // five refs because we forgot to null it.
  const sessionRef = useRef<{
    ws: WebSocket | null;
    stream: MediaStream | null;
    ctx: AudioContext | null;
    workletNode: AudioWorkletNode | null;
    sourceNode: MediaStreamAudioSourceNode | null;
    analyser: AnalyserNode | null;
    rafId: number | null;
    noSpeechTimer: ReturnType<typeof setTimeout> | null;
    abort: AbortController;
  } | null>(null);

  const stop = useCallback(() => {
    const s = sessionRef.current;
    sessionRef.current = null;
    if (!s) {
      // Even when there's no active session, make sure the public state
      // resets — error states clear themselves when the user retries.
      setLevel(0);
      setInterim("");
      setSpeaking(false);
      setState("idle");
      return;
    }
    // Abort first so any in-flight `start()` resumes know to bail out
    // before they touch already-released resources.
    s.abort.abort();

    if (s.rafId !== null) cancelAnimationFrame(s.rafId);
    if (s.noSpeechTimer !== null) clearTimeout(s.noSpeechTimer);

    try {
      s.workletNode?.port.close();
    } catch {
      /* ignore */
    }
    try {
      s.workletNode?.disconnect();
    } catch {
      /* ignore */
    }
    try {
      s.sourceNode?.disconnect();
    } catch {
      /* ignore */
    }
    try {
      s.analyser?.disconnect();
    } catch {
      /* ignore */
    }
    if (s.ctx && s.ctx.state !== "closed") {
      void s.ctx.close().catch(() => undefined);
    }
    if (s.stream) {
      // Releases the OS-level mic indicator promptly.
      s.stream.getTracks().forEach((t) => t.stop());
    }
    if (s.ws && s.ws.readyState <= 1) {
      try {
        s.ws.close();
      } catch {
        /* ignore */
      }
    }

    setLevel(0);
    setInterim("");
    setSpeaking(false);
    setState("idle");
  }, []);

  const start = useCallback(
    async (opts?: VoiceStartOptions) => {
      // Cancel any previous session so two starts in quick succession (e.g.
      // user mashing the mic button) don't end up sharing resources.
      stop();
      setState("connecting");

      const abort = new AbortController();
      const wsUrl = buildWsUrl(opts);
      if (process.env.NODE_ENV !== "production") {
        // eslint-disable-next-line no-console
        console.debug("[voice] connecting", wsUrl);
      }

      const ws = new WebSocket(wsUrl);
      const session = {
        ws,
        stream: null as MediaStream | null,
        ctx: null as AudioContext | null,
        workletNode: null as AudioWorkletNode | null,
        sourceNode: null as MediaStreamAudioSourceNode | null,
        analyser: null as AnalyserNode | null,
        rafId: null as number | null,
        noSpeechTimer: null as ReturnType<typeof setTimeout> | null,
        abort,
      };
      sessionRef.current = session;

      // -----------------------------------------------------------------
      // WS lifecycle
      // -----------------------------------------------------------------

      ws.onopen = async () => {
        if (abort.signal.aborted) return;
        try {
          await setupAudioPipeline(session);
          if (abort.signal.aborted) return;

          setState("listening");

          // If we don't hear anything within N seconds, time out gracefully
          // instead of leaving the mic open forever.
          session.noSpeechTimer = setTimeout(() => {
            cbRef.current.onError?.(
              "Didn't hear anything. Tap to try again.",
              "no_speech",
            );
            setState("error");
            stop();
          }, NO_SPEECH_TIMEOUT_MS);
        } catch (err) {
          if (abort.signal.aborted) return;
          const { message, kind } = classifyMicError(err);
          cbRef.current.onError?.(message, kind);
          setState("error");
          stop();
        }
      };

      ws.onmessage = (ev) => {
        if (abort.signal.aborted) return;
        let msg: VoiceServerEvent;
        try {
          msg = JSON.parse(ev.data) as VoiceServerEvent;
        } catch {
          return;
        }
        if (process.env.NODE_ENV !== "production") {
          // eslint-disable-next-line no-console
          console.debug(
            `[voice ${new Date().toISOString().slice(11, 23)}]`,
            msg.type,
            msg,
          );
        }
        handleServerEvent(msg, session);
      };

      ws.onerror = () => {
        if (abort.signal.aborted) return;
        cbRef.current.onError?.(
          "Couldn't connect to the voice server.",
          "connection",
        );
        setState("error");
      };

      ws.onclose = () => {
        // If we close mid-listen without a transcript, drop back to idle so
        // the user can retry. We don't surface an error if we already showed
        // one (e.g. an `error` event came through right before close).
        setState((s) =>
          s === "listening" || s === "processing" ? "idle" : s,
        );
      };
    },
    // `setupAudioPipeline` and `handleServerEvent` are defined inline
    // below as plain functions; they capture `setState`/`setLevel`/
    // `setInterim`/`setSpeaking`/`cbRef`/`stop` from this closure.
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [stop],
  );

  // Plain helper (defined inside the hook so it captures the setters and
  // refs without needing them in the dependency arrays).
  async function setupAudioPipeline(
    session: NonNullable<typeof sessionRef.current>,
  ): Promise<void> {
    // 1) Mic permission + stream
    const stream = await navigator.mediaDevices.getUserMedia({
      audio: {
        echoCancellation: true,
        noiseSuppression: true,
        channelCount: 1,
      },
    });
    if (session.abort.signal.aborted) {
      stream.getTracks().forEach((t) => t.stop());
      throw new DOMException("aborted", "AbortError");
    }
    session.stream = stream;

    // 2) AudioContext at 24 kHz PCM16 — the rate the worklet emits and that
    //    we tell Deepgram to expect via `sample_rate=24000` on the server.
    const ctx = new AudioContext({ sampleRate: SAMPLE_RATE });
    session.ctx = ctx;

    // 3) Load the AudioWorklet processor (replaces the deprecated
    //    ScriptProcessorNode). The worklet runs encoding off-main-thread.
    await ctx.audioWorklet.addModule(PCM_WORKLET_URL);
    if (session.abort.signal.aborted) {
      throw new DOMException("aborted", "AbortError");
    }

    const sourceNode = ctx.createMediaStreamSource(stream);
    session.sourceNode = sourceNode;

    // 4) Analyser for the waveform amplitude readout.
    const analyser = ctx.createAnalyser();
    analyser.fftSize = 256;
    session.analyser = analyser;

    // 5) Worklet — receives encoded PCM16 buffers and forwards to the WS.
    const workletNode = new AudioWorkletNode(ctx, "pcm16-encoder");
    session.workletNode = workletNode;

    workletNode.port.onmessage = (ev: MessageEvent<ArrayBuffer>) => {
      if (session.abort.signal.aborted) return;
      const ws = session.ws;
      if (!ws || ws.readyState !== WebSocket.OPEN) return;
      // Send the PCM16 ArrayBuffer as a binary WebSocket frame. Deepgram's
      // streaming API consumes raw audio bytes directly — no JSON envelope,
      // no base64. This roughly halves bandwidth and skips the per-chunk
      // string/parse overhead the OpenAI proxy used to require.
      ws.send(ev.data);
    };

    // 6) Wire the graph. The worklet has to terminate at `destination` for
    //    the browser to pump audio through it; we route via a zero-gain
    //    sink so the user doesn't hear themselves.
    sourceNode.connect(analyser);
    sourceNode.connect(workletNode);
    const sink = ctx.createGain();
    sink.gain.value = 0;
    workletNode.connect(sink);
    sink.connect(ctx.destination);

    // 7) RMS level loop for the waveform UI. We multiply by 3 to lift the
    //    typical speech amplitude into a more visually engaging 0–1 range.
    const amp = new Uint8Array(analyser.frequencyBinCount);
    const tick = () => {
      if (session.abort.signal.aborted || !session.analyser) return;
      session.analyser.getByteTimeDomainData(amp);
      let sum = 0;
      for (let i = 0; i < amp.length; i++) {
        const v = (amp[i] - 128) / 128;
        sum += v * v;
      }
      const rms = Math.sqrt(sum / amp.length);
      setLevel(Math.min(1, rms * 3));
      session.rafId = requestAnimationFrame(tick);
    };
    session.rafId = requestAnimationFrame(tick);
  }

  function handleServerEvent(
    msg: VoiceServerEvent,
    session: NonNullable<typeof sessionRef.current>,
  ): void {
    switch (msg.type) {
      case "speech_started": {
        if (session.noSpeechTimer !== null) {
          clearTimeout(session.noSpeechTimer);
          session.noSpeechTimer = null;
        }
        setSpeaking(true);
        setInterim("");
        return;
      }
      case "speech_stopped": {
        setSpeaking(false);
        setState("processing");
        return;
      }
      case "transcript_interim": {
        // Deepgram interim results are full snapshots, not deltas — replace
        // the running interim text wholesale rather than appending.
        const text = (msg as ServerTranscriptInterim).text ?? "";
        setInterim(text);
        return;
      }
      case "transcript_final": {
        const transcript = (msg as ServerTranscriptFinal).text ?? "";
        setInterim(transcript);
        if (!transcript.trim()) {
          cbRef.current.onError?.(
            "I didn't catch that. Try again.",
            "no_speech",
          );
          setState("error");
          return;
        }
        cbRef.current.onTranscript(transcript);
        return;
      }
      case "error": {
        const message = (msg as ServerError).message ?? "Voice server error.";
        cbRef.current.onError?.(message, "connection");
        setState("error");
        return;
      }
      default:
        // Unknown / unhandled event — diagnostic logging picks it up in dev.
        return;
    }
  }

  // Tear down on unmount.
  useEffect(() => {
    return () => stop();
  }, [stop]);

  return { state, level, interim, speaking, start, stop };
}
