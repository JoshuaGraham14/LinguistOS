"use client";

/**
 * Voice mode primitives for sentence practice.
 *
 * Exports:
 * - playTTS: fetches OpenAI TTS audio from the backend and plays it. Caches
 *   blobs by `${text}|${language}` so the same prompt is not refetched when
 *   the user revisits a sentence in the same session.
 * - useVoiceCapture: hook that opens the realtime WebSocket proxy, streams
 *   PCM16 audio from the user's microphone, and reports transcription events
 *   plus a live amplitude level (0-1) for the waveform UI.
 */

import { useCallback, useEffect, useRef, useState } from "react";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

// ---------------------------------------------------------------------------
// TTS
// ---------------------------------------------------------------------------

const ttsCache = new Map<string, string>();

/** Synthesize and play `text`. Resolves when playback finishes. */
export async function playTTS(text: string, language: string): Promise<void> {
  if (!text.trim()) return;
  const key = `${language}|${text}`;
  let url = ttsCache.get(key);
  if (!url) {
    const res = await fetch(`${API_URL}/api/tts`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ text, language }),
    });
    if (!res.ok) throw new Error(`TTS failed: ${res.status}`);
    const blob = await res.blob();
    url = URL.createObjectURL(blob);
    ttsCache.set(key, url);
  }
  await new Promise<void>((resolve, reject) => {
    const audio = new Audio(url);
    audio.onended = () => resolve();
    audio.onerror = () => reject(new Error("audio playback failed"));
    void audio.play().catch(reject);
  });
}

/** Cancel any TTS audio currently playing on a global level. Best-effort. */
export function stopAllTTS() {
  // Audio elements created inside `playTTS` are short-lived and self-cleaning;
  // there's no global registry here. Callers that need hard-stop semantics
  // should keep their own ref. This stub is exported for future use.
}

// ---------------------------------------------------------------------------
// Mic capture + Realtime WebSocket
// ---------------------------------------------------------------------------

export type VoiceState = "idle" | "connecting" | "listening" | "processing" | "error";

export interface VoiceCaptureCallbacks {
  /** Final transcript from OpenAI Realtime. Fired once per user turn. */
  onTranscript: (transcript: string) => void;
  /** Optional: any low-level error from the proxy or mic. */
  onError?: (message: string) => void;
}

/** Encode a Float32 PCM frame to base64 PCM16 little-endian. */
function float32ToPCM16Base64(input: Float32Array): string {
  const buf = new ArrayBuffer(input.length * 2);
  const view = new DataView(buf);
  for (let i = 0; i < input.length; i++) {
    const s = Math.max(-1, Math.min(1, input[i]));
    view.setInt16(i * 2, s < 0 ? s * 0x8000 : s * 0x7fff, true);
  }
  // base64 encode bytes
  const bytes = new Uint8Array(buf);
  let binary = "";
  for (let i = 0; i < bytes.length; i++) binary += String.fromCharCode(bytes[i]);
  return btoa(binary);
}

/**
 * Hook that exposes start/stop controls plus reactive state for one voice
 * capture session. The session is fully torn down whenever `stop` is called
 * or the component unmounts.
 */
/** How long we'll wait for the user to start speaking before giving up. */
const NO_SPEECH_TIMEOUT_MS = 12000;

export function useVoiceCapture(callbacks: VoiceCaptureCallbacks) {
  const [state, setState] = useState<VoiceState>("idle");
  const [level, setLevel] = useState(0); // 0-1, amplitude
  const [interim, setInterim] = useState("");
  // True between `speech_started` and `speech_stopped` from the server VAD.
  // Drives the waveform UI: when speaking, bars track amplitude only (no
  // CSS animation); when listening but quiet, bars do a subtle idle pulse.
  const [speaking, setSpeaking] = useState(false);

  // Latest callbacks live in a ref so we don't have to re-bind WS handlers.
  const cbRef = useRef(callbacks);
  cbRef.current = callbacks;

  const wsRef = useRef<WebSocket | null>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const ctxRef = useRef<AudioContext | null>(null);
  const procRef = useRef<ScriptProcessorNode | null>(null);
  const sourceRef = useRef<MediaStreamAudioSourceNode | null>(null);
  const analyserRef = useRef<AnalyserNode | null>(null);
  const rafRef = useRef<number | null>(null);
  const noSpeechTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const stop = useCallback(() => {
    if (rafRef.current !== null) {
      cancelAnimationFrame(rafRef.current);
      rafRef.current = null;
    }
    if (noSpeechTimerRef.current !== null) {
      clearTimeout(noSpeechTimerRef.current);
      noSpeechTimerRef.current = null;
    }
    try {
      procRef.current?.disconnect();
    } catch {}
    try {
      sourceRef.current?.disconnect();
    } catch {}
    try {
      analyserRef.current?.disconnect();
    } catch {}
    if (ctxRef.current && ctxRef.current.state !== "closed") {
      void ctxRef.current.close().catch(() => undefined);
    }
    if (streamRef.current) {
      streamRef.current.getTracks().forEach((t) => t.stop());
    }
    if (wsRef.current && wsRef.current.readyState <= 1) {
      try {
        wsRef.current.close();
      } catch {}
    }
    procRef.current = null;
    sourceRef.current = null;
    analyserRef.current = null;
    ctxRef.current = null;
    streamRef.current = null;
    wsRef.current = null;
    setLevel(0);
    setInterim("");
    setSpeaking(false);
    setState("idle");
  }, []);

  const start = useCallback(async () => {
    // Tear down any prior session first.
    stop();
    setState("connecting");

    // Build the WS URL from the configured API base, swapping http(s)→ws(s).
    const wsUrl =
      API_URL.replace(/^http/, "ws").replace(/\/$/, "") + "/ws/realtime";

    const ws = new WebSocket(wsUrl);
    wsRef.current = ws;

    ws.onopen = async () => {
      try {
        // Acquire mic. The Realtime API expects 24 kHz PCM16; we resample
        // implicitly by creating an AudioContext at that rate.
        const stream = await navigator.mediaDevices.getUserMedia({
          audio: {
            echoCancellation: true,
            noiseSuppression: true,
            channelCount: 1,
          },
        });
        streamRef.current = stream;

        const ctx = new AudioContext({ sampleRate: 24000 });
        ctxRef.current = ctx;

        const source = ctx.createMediaStreamSource(stream);
        sourceRef.current = source;

        const analyser = ctx.createAnalyser();
        analyser.fftSize = 256;
        analyserRef.current = analyser;

        // ScriptProcessorNode is deprecated but universally supported and
        // adequate for short capture sessions. AudioWorklet is a future
        // upgrade if latency / dropped-frame metrics demand it.
        const proc = ctx.createScriptProcessor(4096, 1, 1);
        procRef.current = proc;

        proc.onaudioprocess = (ev) => {
          if (ws.readyState !== WebSocket.OPEN) return;
          const channel = ev.inputBuffer.getChannelData(0);
          const b64 = float32ToPCM16Base64(channel);
          ws.send(
            JSON.stringify({ type: "input_audio_buffer.append", audio: b64 }),
          );
        };

        source.connect(analyser);
        source.connect(proc);
        // ScriptProcessor only fires `onaudioprocess` if connected to the
        // graph's destination; we mute output via a zero-gain node so the
        // user does not hear themselves echoed.
        const sink = ctx.createGain();
        sink.gain.value = 0;
        proc.connect(sink);
        sink.connect(ctx.destination);

        // Drive the waveform amplitude from the analyser's RMS.
        const amp = new Uint8Array(analyser.frequencyBinCount);
        const tick = () => {
          if (!analyserRef.current) return;
          analyser.getByteTimeDomainData(amp);
          let sum = 0;
          for (let i = 0; i < amp.length; i++) {
            const v = (amp[i] - 128) / 128;
            sum += v * v;
          }
          const rms = Math.sqrt(sum / amp.length);
          // Boost a bit for visual punch; clamp to [0,1].
          setLevel(Math.min(1, rms * 3));
          rafRef.current = requestAnimationFrame(tick);
        };
        rafRef.current = requestAnimationFrame(tick);

        setState("listening");

        // Bail out if the user never speaks within the timeout window. We
        // reset this timer the moment the server VAD reports speech_started.
        noSpeechTimerRef.current = setTimeout(() => {
          cbRef.current.onError?.("Didn't hear anything. Tap to try again.");
          setState("error");
          stop();
        }, NO_SPEECH_TIMEOUT_MS);
      } catch (err) {
        cbRef.current.onError?.(
          err instanceof Error ? err.message : "mic permission denied",
        );
        setState("error");
        stop();
      }
    };

    ws.onmessage = (ev) => {
      let msg: any;
      try {
        msg = JSON.parse(ev.data);
      } catch {
        return;
      }
      const type = msg?.type as string | undefined;
      if (!type) return;

      // Useful for debugging during development; quiet in production.
      if (process.env.NODE_ENV !== "production") {
        if (type === "error" || type.includes("transcription")) {
          // eslint-disable-next-line no-console
          console.debug("[voice]", type, msg);
        }
      }

      if (type === "input_audio_buffer.speech_started") {
        // VAD detected speech — cancel the no-speech timeout.
        if (noSpeechTimerRef.current !== null) {
          clearTimeout(noSpeechTimerRef.current);
          noSpeechTimerRef.current = null;
        }
        setSpeaking(true);
        setInterim("");
      } else if (type === "input_audio_buffer.speech_stopped") {
        setSpeaking(false);
        setState("processing");
      } else if (
        type === "conversation.item.input_audio_transcription.completed"
      ) {
        const transcript: string = msg.transcript ?? "";
        setInterim(transcript);
        // Empty transcripts (just noise) — treat as no-speech and let caller
        // decide whether to show a hint or auto-restart.
        if (!transcript.trim()) {
          cbRef.current.onError?.("I didn't catch that. Try again.");
          setState("error");
          return;
        }
        cbRef.current.onTranscript(transcript);
      } else if (type === "conversation.item.input_audio_transcription.failed") {
        cbRef.current.onError?.(
          msg.error?.message ?? "transcription failed",
        );
        setState("error");
      } else if (type === "error") {
        const message: string =
          msg.error?.message ?? msg.message ?? "realtime error";
        cbRef.current.onError?.(message);
        setState("error");
      }
    };

    ws.onerror = () => {
      cbRef.current.onError?.("websocket error");
      setState("error");
    };

    ws.onclose = () => {
      // If we close while the user expected to keep listening, surface idle.
      setState((s) => (s === "listening" || s === "processing" ? "idle" : s));
    };
  }, [stop]);

  // Always tear down on unmount.
  useEffect(() => {
    return () => stop();
  }, [stop]);

  return { state, level, interim, speaking, start, stop };
}
