"""``POST /api/transcribe``: one spoken phrase to text through OpenRouter.

Request: the raw audio bytes of one phrase as the body (``audio/webm``,
``audio/ogg``, ``audio/mp4`` or ``audio/wav``), ``?lang=en`` optional, and an
optional ``X-ChipIn-Context`` header (URL-encoded, at most 200 characters of
the text dictated just before), passed to the model only as a spelling hint.
The token and origin rules are the server's ``guard`` middleware.

Answer 200 ``{"text", "model", "audio_seconds", "latency_ms"}``; errors are
``{"error": ...}`` with 400 (bad or empty audio), 413 (too large), 429 (over
the hourly audio cap), 502 (the provider failed) or 503 (no key).

Privacy: the audio is held in memory only, and neither the audio nor the
transcript nor the context is written to disk or to the log. The log carries
duration, model, latency and status only.
"""

from __future__ import annotations

import base64
import io
import json
import re
import time
import wave
from array import array
from collections import deque
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any
from urllib.parse import unquote

import httpx
from aiohttp import web
from loguru import logger
from pydantic import BaseModel, ConfigDict, Field

from chipin_backend.llm.endpoints import BASE_URL
from chipin_backend.llm.keys import has_openrouter_key, openrouter_api_key

CONTEXT_HEADER = "X-ChipIn-Context"
CONTEXT_MAX_CHARS = 200
TRANSCRIPTIONS_URL = f"{BASE_URL}/audio/transcriptions"
#: ``model`` of an answer decided locally: a silent WAV never reaches the provider.
SILENCE_MODEL = "silence-check"

#: Request content type -> OpenRouter ``input_audio.format``.
AUDIO_FORMATS: dict[str, str] = {
    "audio/webm": "webm",
    "audio/ogg": "ogg",
    "audio/mp4": "m4a",
    "audio/wav": "wav",
    "audio/wave": "wav",
    "audio/x-wav": "wav",
}

#: Failures before the request reached the provider; nothing can have been billed.
_NOT_SENT = (
    httpx.ConnectError,
    httpx.ConnectTimeout,
    httpx.PoolTimeout,
    httpx.WriteError,
    httpx.WriteTimeout,
)

#: Phrases speech models are known to invent for silence or noise (Whisper's
#: training captions). A transcript that is only one of these is treated as empty.
_SILENCE_PHRASES = frozenset(
    {
        "",
        "you",
        "thank you",
        "thanks",
        "thank you for watching",
        "thanks for watching",
        "bye",
        "music",
        "applause",
        "silence",
        "subtitles by the amara org community",
    }
)
_PUNCTUATION = re.compile(r"[^\w\s]+")
#: Sound tags some models emit for non-speech, such as ``[pause]`` or ``(music)``.
_SOUND_TAG = re.compile(r"\[[^\]]*\]|\([^)]*\)|\*[^*]*\*")


class TranscribeConfig(BaseModel):
    """The ``transcribe`` block of ``api.yaml``."""

    model_config = ConfigDict(extra="forbid")

    enabled: bool = True
    model: str = "openai/gpt-transcribe"
    fallback_model: str | None = "elevenlabs/scribe-v2"
    language: str = "en"
    max_bytes: int = Field(default=2 * 1024 * 1024, gt=0)
    max_audio_s: float = Field(default=30.0, gt=0)
    hourly_audio_s: float = Field(default=1800.0, ge=0)
    timeout_s: float = Field(default=30.0, gt=0)
    # A WAV body whose loudest stretch stays under this RMS (16-bit scale) is
    # silence and never reaches the provider.
    silence_rms: float = Field(default=200.0, ge=0)


@dataclass(frozen=True)
class SttResult:
    """One provider answer."""

    text: str
    seconds: float | None = None


class ProviderError(RuntimeError):
    """The provider failed; ``status`` is its HTTP status (``None`` for transport).

    ``sent`` says the request may have reached the provider (a retry or a
    fallback could pay twice).
    """

    def __init__(self, status: int | None, *, sent: bool) -> None:
        self.status = status
        self.sent = sent
        super().__init__(f"transcription provider failed (status {status})")


@dataclass(frozen=True)
class SttRequest:
    """What a provider call needs; never logged."""

    audio: bytes
    audio_format: str
    model: str
    language: str
    prompt: str | None
    timeout_s: float


Provider = Callable[[SttRequest], Awaitable[SttResult]]


class AudioBudget:
    """Seconds of audio transcribed in a rolling window, against a cap."""

    def __init__(self, limit_s: float, window_s: float = 3600.0, clock: Callable[[], float] = time.monotonic):
        self.limit_s = limit_s
        self.window_s = window_s
        self._clock = clock
        self._spent: deque[tuple[float, float]] = deque()

    def used(self) -> float:
        """Seconds spent inside the window."""
        cutoff = self._clock() - self.window_s
        while self._spent and self._spent[0][0] <= cutoff:
            self._spent.popleft()
        return sum(seconds for _, seconds in self._spent)

    def exhausted(self) -> bool:
        """Whether the cap is already reached."""
        return self.used() >= self.limit_s

    def spend(self, seconds: float) -> None:
        """Record ``seconds`` of audio now."""
        if seconds > 0:
            self._spent.append((self._clock(), seconds))


async def openrouter_stt(req: SttRequest) -> SttResult:
    """One ``POST /audio/transcriptions`` call (JSON body, base64 audio).

    A transport error before any byte of the answer arrived is retried once;
    a failure after the answer started is not. The provider's own error text
    is never passed on: :class:`ProviderError` carries the status only.
    """
    payload: dict[str, Any] = {
        "model": req.model,
        "input_audio": {"data": base64.b64encode(req.audio).decode("ascii"), "format": req.audio_format},
        "language": req.language,
        "temperature": 0,
    }
    if req.prompt:
        payload["prompt"] = req.prompt
    headers = {"Authorization": f"Bearer {openrouter_api_key()}"}
    async with httpx.AsyncClient(timeout=req.timeout_s) as http:
        request = http.build_request("POST", TRANSCRIPTIONS_URL, json=payload, headers=headers)
        for attempt in (1, 2):
            try:
                response = await http.send(request, stream=True)
                break
            except httpx.TransportError as exc:
                if attempt == 2:
                    raise ProviderError(None, sent=not isinstance(exc, _NOT_SENT)) from exc
        try:
            await response.aread()
        except httpx.TransportError as exc:
            raise ProviderError(response.status_code, sent=True) from exc
        finally:
            await response.aclose()
    if response.is_error:
        raise ProviderError(response.status_code, sent=True)
    try:
        data = response.json()
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise ProviderError(response.status_code, sent=True) from exc
    text = data.get("text") if isinstance(data, dict) else None
    if not isinstance(text, str):
        raise ProviderError(response.status_code, sent=True)
    usage = data.get("usage") or {}
    seconds = usage.get("seconds") if isinstance(usage, dict) else None
    return SttResult(text=text, seconds=float(seconds) if isinstance(seconds, int | float) else None)


def wav_stats(audio: bytes) -> tuple[float, float] | None:
    """``(seconds, peak_rms)`` of a PCM WAV body, or ``None`` if it is not one.

    ``peak_rms`` is the loudest 50 ms window on a 16-bit scale (other sample
    widths are rescaled), so a short word in a quiet clip still counts.
    """
    try:
        with wave.open(io.BytesIO(audio), "rb") as wav:
            rate, width, channels = wav.getframerate(), wav.getsampwidth(), wav.getnchannels()
            frames = wav.readframes(wav.getnframes())
    except (wave.Error, EOFError):
        return None
    if rate <= 0 or channels <= 0 or width not in (1, 2, 4):
        return None
    seconds = len(frames) / (rate * width * channels)
    samples = _samples(frames, width)
    if not samples:
        return seconds, 0.0
    step = max(int(rate * channels * 0.05), 1)
    peak = 0.0
    for start in range(0, len(samples), step):
        chunk = samples[start : start + step]
        rms = (sum(s * s for s in chunk) / len(chunk)) ** 0.5
        peak = max(peak, rms)
    return seconds, peak


def _samples(frames: bytes, width: int) -> list[float]:
    """PCM samples rescaled to the 16-bit range."""
    if width == 1:
        return [(b - 128) * 256.0 for b in frames]
    typecode = "h" if width == 2 else "i"
    values = array(typecode)
    usable = len(frames) - len(frames) % width
    values.frombytes(frames[:usable])
    scale = 1.0 if width == 2 else 1 / 65536
    return [v * scale for v in values]


def clean_transcript(text: str) -> str:
    """The transcript stripped, or ``""`` if it is only sound tags or a known silence phrase."""
    text = text.strip()
    normal = _PUNCTUATION.sub(" ", _SOUND_TAG.sub(" ", text.lower())).split()
    return "" if " ".join(normal) in _SILENCE_PHRASES else text


def context_hint(raw: str | None) -> str | None:
    """The decoded ``X-ChipIn-Context`` value, last 200 characters, or ``None``."""
    if not raw:
        return None
    text = " ".join(unquote(raw).split())
    return text[-CONTEXT_MAX_CHARS:] or None


@dataclass
class TranscribeState:
    """Per-app state of the endpoint."""

    config: TranscribeConfig
    budget: AudioBudget
    provider: Provider


TRANSCRIBE = web.AppKey("transcribe", TranscribeState)


def transcribe_ready(app: web.Application) -> bool:
    """Whether the endpoint is on and a key is configured (for ``/api/health``)."""
    state = app.get(TRANSCRIBE)
    return state is not None and state.config.enabled and has_openrouter_key()


def _error(message: str, status: int) -> web.Response:
    return web.json_response({"error": message}, status=status)


async def _read_capped(request: web.Request, cap: int) -> bytes | None:
    """The body, or ``None`` as soon as it passes ``cap`` bytes (never buffers more)."""
    if request.content_length is not None and request.content_length > cap:
        return None
    body = bytearray()
    while True:
        chunk = await request.content.read(min(64 * 1024, cap + 1 - len(body)))
        if not chunk:
            return bytes(body)
        body += chunk
        if len(body) > cap:
            return None


async def _call(state: TranscribeState, req: SttRequest) -> tuple[SttResult, str]:
    """The primary model, then the fallback model once when the primary fails."""
    try:
        return await state.provider(req), req.model
    except ProviderError as exc:
        fallback = state.config.fallback_model
        if not fallback or fallback == req.model:
            raise
        logger.warning("transcribe: {} failed (status {}); trying the fallback", req.model, exc.status)
    alt = SttRequest(**{**req.__dict__, "model": fallback})
    return await state.provider(alt), fallback


async def transcribe(request: web.Request) -> web.Response:
    """``POST /api/transcribe``."""
    state = request.app[TRANSCRIBE]
    cfg = state.config
    started = time.monotonic()
    if not cfg.enabled:
        return _error("transcription is turned off in api.yaml", 503)
    if not has_openrouter_key():
        return _error("transcription needs OPENROUTER_API_KEY, which is not set on this server", 503)
    audio_format = AUDIO_FORMATS.get(request.content_type)
    if audio_format is None:
        return _error("send audio/webm, audio/ogg, audio/mp4 or audio/wav", 400)
    audio = await _read_capped(request, cfg.max_bytes)
    if audio is None:
        return _error(f"audio larger than {cfg.max_bytes} bytes", 413)
    if not audio:
        return _error("no audio in the body", 400)
    language = request.query.get("lang", cfg.language).strip().lower()
    if not re.fullmatch(r"[a-z]{2,3}", language):
        return _error("lang must be an ISO-639-1 code such as en", 400)
    estimate: float | None = None
    if audio_format == "wav":
        stats = wav_stats(audio)
        if stats is None:
            return _error("the body is not a readable WAV file", 400)
        estimate, peak = stats
        if estimate <= 0:
            return _error("no audio in the body", 400)
        if estimate > cfg.max_audio_s:
            return _error(f"audio longer than {cfg.max_audio_s:g} s", 413)
        if peak < cfg.silence_rms:
            return _done("", SILENCE_MODEL, estimate, started)
    if state.budget.exhausted():
        logger.info("transcribe: 429 hourly audio cap reached")
        return _error("over the hourly transcription cap; try again later", 429)
    req = SttRequest(
        audio=audio,
        audio_format=audio_format,
        model=cfg.model,
        language=language,
        prompt=context_hint(request.headers.get(CONTEXT_HEADER)),
        timeout_s=cfg.timeout_s,
    )
    try:
        result, model = await _call(state, req)
    except ProviderError as exc:
        latency = round((time.monotonic() - started) * 1000)
        logger.warning("transcribe: 502 provider status {} after {} ms", exc.status, latency)
        return _error("the transcription provider failed; try again", 502)
    seconds = result.seconds if result.seconds is not None else (estimate or 0.0)
    state.budget.spend(seconds)
    return _done(clean_transcript(result.text), model, seconds, started)


def _done(text: str, model: str, seconds: float, started: float) -> web.Response:
    """The 200 answer, logged without the text."""
    latency = round((time.monotonic() - started) * 1000)
    logger.info("transcribe: 200 model {} audio {:.1f}s latency {} ms", model, seconds, latency)
    body = {"text": text, "model": model, "audio_seconds": round(seconds, 2), "latency_ms": latency}
    return web.json_response(body)


def add_transcribe_route(
    app: web.Application, config: TranscribeConfig, provider: Provider | None = None
) -> None:
    """Register ``POST /api/transcribe`` with its state on ``app``."""
    app[TRANSCRIBE] = TranscribeState(
        config=config, budget=AudioBudget(config.hourly_audio_s), provider=provider or openrouter_stt
    )
    app.router.add_post("/api/transcribe", transcribe)


__all__ = [
    "AUDIO_FORMATS",
    "CONTEXT_HEADER",
    "SILENCE_MODEL",
    "TRANSCRIBE",
    "AudioBudget",
    "ProviderError",
    "SttRequest",
    "SttResult",
    "TranscribeConfig",
    "add_transcribe_route",
    "clean_transcript",
    "context_hint",
    "openrouter_stt",
    "transcribe_ready",
    "wav_stats",
]
