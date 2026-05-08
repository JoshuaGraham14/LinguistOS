"""Voice mode endpoints.

Provides:
- POST /api/tts: text-to-speech via OpenAI TTS, returns audio/mpeg.
- WS  /ws/realtime: bidirectional proxy to Deepgram's streaming speech-to-text
  API (Nova-3). The browser cannot connect directly because the API key must
  not leave the server, so this route relays audio upstream and translates
  Deepgram's wire format into a stable internal event protocol shaped for
  our UI.

Why two providers?
  OpenAI TTS (`tts-1`) produces high-quality MP3 audio that streams natively
  via the <audio> element. Deepgram Nova-3 was purpose-built for non-native
  multilingual ASR with true interim results during speech and a first-class
  `keyterm` parameter for vocabulary biasing — exactly what a language-
  learning app needs. We use each provider for what it does best.
"""

from __future__ import annotations

import asyncio
import json
import logging
import ssl
from typing import Literal
from urllib.parse import urlencode

import certifi
import websockets
from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.responses import StreamingResponse
from openai import OpenAI
from pydantic import BaseModel

from app.config import settings

logger = logging.getLogger(__name__)

router = APIRouter()

# Single OpenAI client reused across requests (TTS only; the Deepgram proxy
# uses raw websockets to keep streaming control).
_openai_client: OpenAI | None = None


def _client() -> OpenAI:
    global _openai_client
    if _openai_client is None:
        if not settings.openai_api_key:
            raise HTTPException(
                status_code=503,
                detail="OPENAI_API_KEY is not configured on the server.",
            )
        _openai_client = OpenAI(api_key=settings.openai_api_key)
    return _openai_client


# ---------------------------------------------------------------------------
# TTS
# ---------------------------------------------------------------------------

# Map language code -> default voice. OpenAI TTS voices are multilingual, but
# different voices have different timbres and quality profiles per language.
# Defaulting to "nova" everywhere keeps the UX consistent across workspaces;
# tweak per-language if dissertation testing reveals quality differences.
_VOICE_BY_LANG: dict[str, str] = {
    "en": "nova",
    "es": "nova",
    "fr": "nova",
    "he": "nova",
}


class TTSRequest(BaseModel):
    text: str
    language: Literal["en", "es", "fr", "he"] = "es"


def _stream_tts(text: str, language: str):
    """Yield MP3 bytes from OpenAI TTS as they arrive.

    Using `with_streaming_response` means we start emitting bytes downstream
    as soon as OpenAI starts producing them, instead of buffering the whole
    file. Combined with a GET endpoint on the client (which lets the browser
    use native progressive download via the <audio> element), this cuts the
    perceived TTS latency roughly in half on a warm network.
    """
    voice = _VOICE_BY_LANG.get(language, "nova")
    try:
        with _client().audio.speech.with_streaming_response.create(
            model="tts-1",
            voice=voice,
            input=text,
            response_format="mp3",
        ) as response:
            for chunk in response.iter_bytes(chunk_size=4096):
                if chunk:
                    yield chunk
    except Exception:  # pragma: no cover - network errors
        logger.exception("OpenAI TTS request failed")
        # Re-raising mid-stream surfaces a 500 to the client; on warm network
        # this only happens if OpenAI itself errors.
        raise


@router.get("/api/tts")
def synthesize_speech_get(
    text: str,
    language: Literal["en", "es", "fr", "he"] = "es",
) -> StreamingResponse:
    """GET variant: lets <audio src=...> stream natively + browser-cache.

    Browsers progressively decode MP3 from the response body, so playback
    can start before the full file is downloaded. The Cache-Control header
    plus stable URL params (text + language) means revisiting a prompt is
    instant from disk cache.
    """
    text = text.strip()
    if not text:
        raise HTTPException(status_code=400, detail="text must not be empty")
    return StreamingResponse(
        _stream_tts(text, language),
        media_type="audio/mpeg",
        headers={"Cache-Control": "public, max-age=3600"},
    )


@router.post("/api/tts")
def synthesize_speech(req: TTSRequest) -> StreamingResponse:
    """Legacy POST kept for back-compat; same streaming under the hood."""
    text = req.text.strip()
    if not text:
        raise HTTPException(status_code=400, detail="text must not be empty")
    return StreamingResponse(
        _stream_tts(text, req.language),
        media_type="audio/mpeg",
        headers={"Cache-Control": "public, max-age=3600"},
    )


# ---------------------------------------------------------------------------
# Deepgram Nova-3 WebSocket proxy
# ---------------------------------------------------------------------------

# Nova-3 is Deepgram's flagship multilingual ASR. It supports en/es/fr/he
# (and 50+ others), exposes word-level timings, and accepts `keyterm` query
# params for vocabulary biasing — the documented technique for boosting
# recognition of expected phrases by up to 90% Keyword Recall Rate.
_DEEPGRAM_URL = "wss://api.deepgram.com/v1/listen"

# Languages we lock transcription to. Deepgram uses ISO-639-1 codes, same as
# OpenAI did. Pinning the language stops the model from drifting (e.g.,
# Spanish → Italian) when accent confidence is low.
_SUPPORTED_TRANSCRIBE_LANGS = {"en", "es", "fr", "he"}

# Sample rate of the PCM16 stream the browser sends. Must match the AudioContext
# rate set in voice.ts. Kept in sync via this constant for readability.
_SAMPLE_RATE = 24000

# Hard cap on keyterms per Deepgram's docs (500 tokens, ~100 terms). Our
# expected sentences never approach this, but we guard against pathological
# input just in case.
_MAX_KEYTERMS = 100


def _build_keyterms(expected: str) -> list[str]:
    """Extract unique words from `expected` for `keyterm=` boosting.

    Deepgram's keyterm feature biases the decoder toward specific words by
    weighting their phonemes — exactly what we want when the learner is
    *trying* to say a known canonical sentence. We strip punctuation,
    deduplicate case-insensitively, and preserve original case (which lets
    Deepgram learn capitalization for proper nouns when smart_format is on).
    """
    seen: set[str] = set()
    out: list[str] = []
    for raw in expected.split():
        word = raw.strip(".,!?¿¡;:\"'“”„«»…—–-")
        if not word:
            continue
        key = word.lower()
        if key in seen:
            continue
        seen.add(key)
        out.append(word)
        if len(out) >= _MAX_KEYTERMS:
            break
    return out


def _build_deepgram_url(language: str | None, expected: str | None) -> str:
    """Construct the Deepgram listen URL with all streaming params.

    Each parameter earns its place:

      model=nova-3            best accuracy on accented multilingual speech
      language=<iso>          pin to one language (avoid auto-detect drift)
      encoding=linear16       raw PCM16 from our worklet
      sample_rate=24000       matches AudioContext on the client
      channels=1              mono (matches getUserMedia config)
      interim_results=true    stream deltas during speech — the live UX win
      smart_format=true       proper punctuation/capitalisation for readback
      vad_events=true         emit SpeechStarted events for UI state
      utterance_end_ms=1000   fire UtteranceEnd after 1s silence (failsafe)
      endpointing=300         mark speech_final=true at 300ms pause
      keyterm=<word>          (repeated) vocabulary biasing toward expected
    """
    # `urlencode` with `doseq=True` correctly emits `keyterm=foo&keyterm=bar`
    # rather than a single comma-joined param, which is the format Deepgram
    # documents for boosting individual terms.
    params: list[tuple[str, str]] = [
        ("model", "nova-3"),
        ("encoding", "linear16"),
        ("sample_rate", str(_SAMPLE_RATE)),
        ("channels", "1"),
        ("interim_results", "true"),
        ("smart_format", "true"),
        ("vad_events", "true"),
        ("utterance_end_ms", "1000"),
        ("endpointing", "300"),
    ]
    if language and language in _SUPPORTED_TRANSCRIBE_LANGS:
        params.append(("language", language))
    if expected:
        for word in _build_keyterms(expected):
            params.append(("keyterm", word))
    return f"{_DEEPGRAM_URL}?{urlencode(params)}"


@router.websocket("/ws/realtime")
async def realtime_proxy(
    client_ws: WebSocket,
    language: str | None = None,
    expected: str | None = None,
) -> None:
    """Bidirectional proxy between the browser and Deepgram's streaming API.

    The browser sends raw PCM16 audio as binary WebSocket frames. We forward
    the bytes verbatim upstream and translate Deepgram's JSON event stream
    into a stable internal protocol consumed by `frontend/lib/voice.ts`:

      {type: "speech_started"}
      {type: "speech_stopped"}
      {type: "transcript_interim", text: "..."}
      {type: "transcript_final",   text: "..."}
      {type: "error",              message: "..."}

    Query params:
      `language` — ISO-639-1 code; pins transcription to that language.
      `expected` — canonical sentence; each unique word becomes a `keyterm=`
                   on Deepgram for vocabulary biasing.
    """
    await client_ws.accept()

    if not settings.deepgram_api_key:
        await client_ws.send_json(
            {"type": "error", "message": "DEEPGRAM_API_KEY not configured"}
        )
        await client_ws.close()
        return

    # Deepgram authenticates with `Authorization: Token <key>` (NOT Bearer).
    headers = {"Authorization": f"Token {settings.deepgram_api_key}"}
    url = _build_deepgram_url(language, expected)

    # certifi CA bundle so wss:// works on macOS Python installs that don't
    # trust the system keychain. Same fix that was needed for OpenAI.
    ssl_ctx = ssl.create_default_context(cafile=certifi.where())

    try:
        async with websockets.connect(
            url,
            additional_headers=headers,
            ssl=ssl_ctx,
            max_size=None,  # audio frames can be large
        ) as upstream:
            # Deepgram doesn't need a session.update message — all config
            # comes from query params, so we connect-and-go.

            async def client_to_upstream() -> None:
                """Forward audio (binary) and control messages (text) upstream.

                The browser sends raw PCM16 ArrayBuffers as binary frames
                (Deepgram's native input format), which is roughly half the
                bandwidth of the previous base64-wrapped JSON approach and
                drops the JSON-parse cost entirely.
                """
                try:
                    while True:
                        msg = await client_ws.receive()
                        # FastAPI's `receive()` returns a dict with either
                        # "bytes" or "text" set, plus a "type" telling us
                        # about disconnects.
                        if msg.get("type") == "websocket.disconnect":
                            break
                        data_bytes = msg.get("bytes")
                        if data_bytes is not None:
                            await upstream.send(data_bytes)
                            continue
                        data_text = msg.get("text")
                        if data_text is not None:
                            # Reserved for future control messages
                            # (CloseStream, KeepAlive). Currently the client
                            # only sends audio.
                            await upstream.send(data_text)
                except WebSocketDisconnect:
                    pass
                except Exception:  # pragma: no cover - network errors
                    logger.exception("client→upstream relay failed")
                finally:
                    # Tell Deepgram we're done so it flushes any pending
                    # final transcripts before closing.
                    try:
                        await upstream.send(json.dumps({"type": "CloseStream"}))
                    except Exception:
                        pass

            async def upstream_to_client() -> None:
                """Translate Deepgram events to our internal protocol."""
                final_buffer: list[str] = []
                try:
                    async for raw in upstream:
                        if isinstance(raw, bytes):
                            raw = raw.decode("utf-8", errors="replace")
                        try:
                            evt = json.loads(raw)
                        except json.JSONDecodeError:
                            continue

                        t = evt.get("type")
                        if t == "Results":
                            alt = (
                                evt.get("channel", {})
                                .get("alternatives", [{}])[0]
                            )
                            text = (alt.get("transcript") or "").strip()
                            if not text:
                                # Silent frames produce empty transcripts;
                                # skip to avoid flickering the UI.
                                continue
                            is_final = bool(evt.get("is_final"))
                            speech_final = bool(evt.get("speech_final"))
                            if not is_final:
                                # Deepgram interim results REPLACE the
                                # current interim text per frame (unlike
                                # OpenAI's additive deltas), so we just
                                # forward the latest snapshot.
                                await client_ws.send_json(
                                    {"type": "transcript_interim", "text": text}
                                )
                            else:
                                final_buffer.append(text)
                                if speech_final:
                                    await client_ws.send_json(
                                        {
                                            "type": "transcript_final",
                                            "text": " ".join(final_buffer).strip(),
                                        }
                                    )
                                    final_buffer.clear()
                        elif t == "SpeechStarted":
                            await client_ws.send_json({"type": "speech_started"})
                        elif t == "UtteranceEnd":
                            # Failsafe: if endpointing didn't fire
                            # speech_final, flush whatever we have here.
                            if final_buffer:
                                await client_ws.send_json(
                                    {
                                        "type": "transcript_final",
                                        "text": " ".join(final_buffer).strip(),
                                    }
                                )
                                final_buffer.clear()
                            await client_ws.send_json({"type": "speech_stopped"})
                        # Metadata, Error, and other event types are
                        # intentionally ignored — Deepgram surfaces fatal
                        # errors via the WebSocket close code instead.
                except websockets.ConnectionClosed:
                    return
                except Exception:  # pragma: no cover - network errors
                    logger.exception("upstream→client relay failed")

            # Run both relays concurrently. When either finishes (disconnect
            # or error) cancel the other and tear the proxy down.
            tasks = [
                asyncio.create_task(client_to_upstream()),
                asyncio.create_task(upstream_to_client()),
            ]
            _done, pending = await asyncio.wait(
                tasks, return_when=asyncio.FIRST_COMPLETED
            )
            for t in pending:
                t.cancel()
    except WebSocketDisconnect:
        return
    except Exception as exc:  # pragma: no cover - network errors
        logger.exception("Deepgram proxy error")
        try:
            await client_ws.send_json(
                {"type": "error", "message": f"proxy error: {exc}"}
            )
        except Exception:
            pass
    finally:
        try:
            await client_ws.close()
        except Exception:
            pass
