"""Voice mode endpoints.

Provides:
- POST /api/tts: text-to-speech via OpenAI TTS, returns audio/mpeg.
- WS  /ws/realtime: bidirectional proxy to OpenAI Realtime API for streaming
  speech-to-text. The browser cannot connect directly because the API key must
  not leave the server, so this route relays JSON events both ways.

The Realtime API is configured for transcription only (no model audio output);
we use OpenAI TTS separately for prompt playback so we can cache audio per
sentence and pick the right voice/language.
"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Literal

import websockets
from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.responses import StreamingResponse
from openai import OpenAI
from pydantic import BaseModel

from app.config import settings

logger = logging.getLogger(__name__)

router = APIRouter()

# Single OpenAI client reused across requests (TTS only; the Realtime proxy
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


@router.post("/api/tts")
def synthesize_speech(req: TTSRequest) -> StreamingResponse:
    """Generate speech audio for the given text. Returns MP3 bytes."""
    text = req.text.strip()
    if not text:
        raise HTTPException(status_code=400, detail="text must not be empty")

    voice = _VOICE_BY_LANG.get(req.language, "nova")

    try:
        # The streaming response form lets us pipe the bytes back without
        # buffering the entire MP3 in memory. For short prompt/answer audio
        # (typically under a few KB) the difference is negligible, but it's
        # the cleaner pattern.
        response = _client().audio.speech.create(
            model="tts-1",
            voice=voice,
            input=text,
            response_format="mp3",
        )
    except Exception as exc:  # pragma: no cover - network errors
        logger.exception("OpenAI TTS request failed")
        raise HTTPException(status_code=502, detail=f"TTS upstream error: {exc}") from exc

    audio_bytes: bytes = response.content
    return StreamingResponse(
        iter([audio_bytes]),
        media_type="audio/mpeg",
        headers={
            "Cache-Control": "public, max-age=3600",
            "Content-Length": str(len(audio_bytes)),
        },
    )


# ---------------------------------------------------------------------------
# Realtime API WebSocket proxy
# ---------------------------------------------------------------------------

# OpenAI's Realtime API endpoint (preview model as of the planning date).
_REALTIME_URL = "wss://api.openai.com/v1/realtime?model=gpt-4o-realtime-preview"

# Initial session configuration sent right after the upstream socket opens.
# We disable audio modality on the model side because we only need
# transcription; TTS is handled by a separate REST call.
_SESSION_UPDATE = {
    "type": "session.update",
    "session": {
        "modalities": ["text"],
        "input_audio_format": "pcm16",
        "input_audio_transcription": {"model": "whisper-1"},
        "turn_detection": {
            "type": "server_vad",
            "threshold": 0.5,
            "prefix_padding_ms": 300,
            "silence_duration_ms": 600,
        },
    },
}


@router.websocket("/ws/realtime")
async def realtime_proxy(client_ws: WebSocket) -> None:
    """Bidirectional proxy between the browser and OpenAI's Realtime API."""
    await client_ws.accept()

    if not settings.openai_api_key:
        await client_ws.send_json(
            {"type": "error", "error": {"message": "OPENAI_API_KEY not configured"}}
        )
        await client_ws.close()
        return

    headers = {
        "Authorization": f"Bearer {settings.openai_api_key}",
        "OpenAI-Beta": "realtime=v1",
    }

    try:
        async with websockets.connect(
            _REALTIME_URL,
            additional_headers=headers,
            max_size=None,  # audio frames can be large
        ) as upstream:
            # Configure the session for transcription-only mode.
            await upstream.send(json.dumps(_SESSION_UPDATE))

            async def client_to_upstream() -> None:
                """Forward client audio chunks / control messages upstream."""
                try:
                    while True:
                        msg = await client_ws.receive_text()
                        await upstream.send(msg)
                except WebSocketDisconnect:
                    return
                except Exception:  # pragma: no cover
                    logger.exception("client→upstream relay failed")

            async def upstream_to_client() -> None:
                """Forward Realtime events back to the browser."""
                try:
                    async for raw in upstream:
                        # raw is str for text frames; pass through verbatim so
                        # the frontend sees the official event schema.
                        if isinstance(raw, bytes):
                            raw = raw.decode("utf-8", errors="replace")
                        await client_ws.send_text(raw)
                except websockets.ConnectionClosed:
                    return
                except Exception:  # pragma: no cover
                    logger.exception("upstream→client relay failed")

            # Run both relays concurrently. When either finishes (disconnect or
            # error) we cancel the other and tear the proxy down.
            tasks = [
                asyncio.create_task(client_to_upstream()),
                asyncio.create_task(upstream_to_client()),
            ]
            done, pending = await asyncio.wait(
                tasks, return_when=asyncio.FIRST_COMPLETED
            )
            for t in pending:
                t.cancel()
    except WebSocketDisconnect:
        return
    except Exception as exc:  # pragma: no cover
        logger.exception("Realtime proxy error")
        try:
            await client_ws.send_json(
                {"type": "error", "error": {"message": f"proxy error: {exc}"}}
            )
        except Exception:
            pass
    finally:
        try:
            await client_ws.close()
        except Exception:
            pass
