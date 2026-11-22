"""``POST /api/transcribe`` with a faked provider: every status of the contract, no paid calls."""

from __future__ import annotations

import functools
import io
import json
import math
import wave
from array import array
from collections.abc import AsyncIterator, Iterator
from pathlib import Path
from typing import Any

import httpx
import pytest
from aiohttp.test_utils import TestClient, TestServer
from loguru import logger

from chipin_backend.api import transcribe as tr
from chipin_backend.api.config import ApiConfig, load_api_config
from chipin_backend.api.server import TOKEN_HEADER, create_app
from chipin_backend.api.transcribe import (
    CONTEXT_HEADER,
    TRANSCRIBE,
    AudioBudget,
    ProviderError,
    SttRequest,
    SttResult,
    TranscribeConfig,
    clean_transcript,
    context_hint,
    openrouter_stt,
)
from chipin_backend.config import BackendConfig

TOKEN = "test-session-token"
AUTH = {TOKEN_HEADER: TOKEN}
SPOKEN = "a seizure alarm for a four channel headband"
URL = "/api/transcribe"


def _wav(seconds: float = 1.0, amplitude: int = 8000, rate: int = 16000) -> bytes:
    """A mono 16-bit sine (``amplitude`` 0 is silence)."""
    samples = array(
        "h", (int(amplitude * math.sin(2 * math.pi * 440 * i / rate)) for i in range(int(seconds * rate)))
    )
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(rate)
        wav.writeframes(samples.tobytes())
    return buf.getvalue()


class FakeProvider:
    """Records requests; answers ``text``, or fails for the models in ``failing``."""

    def __init__(self, text: str = SPOKEN, failing: frozenset[str] = frozenset()) -> None:
        self.text = text
        self.failing = failing
        self.calls: list[SttRequest] = []

    async def __call__(self, req: SttRequest) -> SttResult:
        self.calls.append(req)
        if req.model in self.failing:
            raise ProviderError(500, sent=True)
        return SttResult(text=self.text, seconds=2.0)


@pytest.fixture
def key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OPENROUTER_API_KEY", "fake-key-for-tests")


async def _client(config: BackendConfig, provider: FakeProvider, **cfg: Any) -> TestClient:
    api = ApiConfig(transcribe=TranscribeConfig(**cfg))
    app = create_app(config, api, token=TOKEN, agent="stub")
    app[TRANSCRIBE].provider = provider
    return TestClient(TestServer(app))


@pytest.fixture
def provider() -> FakeProvider:
    return FakeProvider()


@pytest.fixture
async def client(config: BackendConfig, provider: FakeProvider, key: None) -> AsyncIterator[TestClient]:
    async with await _client(config, provider) as c:
        yield c


def _post(client: TestClient, body: bytes, ctype: str = "audio/wav", **headers: str) -> Any:
    return client.post(URL, data=body, headers={"Content-Type": ctype, **AUTH, **headers})


# ---- 200 ----


async def test_transcribes_one_phrase(client: TestClient, provider: FakeProvider) -> None:
    resp = await client.post(
        URL,
        params={"lang": "de"},
        data=_wav(1.5),
        headers={"Content-Type": "audio/wav", CONTEXT_HEADER: "EEG%20headband%2C%20256%20Hz", **AUTH},
    )
    assert resp.status == 200
    body = await resp.json()
    assert body["text"] == SPOKEN
    assert body["model"] == "openai/gpt-transcribe"
    assert body["audio_seconds"] == 2.0
    assert isinstance(body["latency_ms"], int)
    (req,) = provider.calls
    assert (req.audio_format, req.language, req.prompt) == ("wav", "de", "EEG headband, 256 Hz")


@pytest.mark.parametrize(
    ("ctype", "fmt"), [("audio/webm", "webm"), ("audio/ogg", "ogg"), ("audio/mp4", "m4a")]
)
async def test_compressed_formats_go_to_the_provider(
    client: TestClient, provider: FakeProvider, ctype: str, fmt: str
) -> None:
    resp = await _post(client, b"\x1a\x45\xdf\xa3 compressed bytes", f"{ctype}; codecs=opus")
    assert resp.status == 200
    assert provider.calls[0].audio_format == fmt


async def test_fallback_model_when_the_first_fails(config: BackendConfig, key: None) -> None:
    provider = FakeProvider(failing=frozenset({"openai/gpt-transcribe"}))
    async with await _client(config, provider) as c:
        resp = await _post(c, _wav())
        assert resp.status == 200
        assert (await resp.json())["model"] == "elevenlabs/scribe-v2"
    assert [r.model for r in provider.calls] == ["openai/gpt-transcribe", "elevenlabs/scribe-v2"]


# ---- silence and noise ----


async def test_silent_wav_is_empty_without_a_call(client: TestClient, provider: FakeProvider) -> None:
    resp = await _post(client, _wav(2.0, amplitude=0))
    assert resp.status == 200
    assert (await resp.json())["text"] == ""
    assert provider.calls == []


@pytest.mark.parametrize("text", ["", "  ", "Thank you.", "you", "[pause]", "(music) [noise]", "*silence*"])
async def test_invented_words_for_noise_become_empty(config: BackendConfig, key: None, text: str) -> None:
    async with await _client(config, FakeProvider(text=text)) as c:
        resp = await _post(c, _wav())
        assert (await resp.json())["text"] == ""


def test_clean_transcript_keeps_real_speech() -> None:
    assert clean_transcript("  Thank you for the dialysis data. ") == "Thank you for the dialysis data."


def test_context_hint() -> None:
    assert context_hint(None) is None
    assert context_hint("%20%20") is None
    assert context_hint("x" * 300 + "%20end") == ("x" * 300 + " end")[-200:]


# ---- 400 ----


async def test_bad_or_empty_audio_is_400(client: TestClient, provider: FakeProvider) -> None:
    assert (await _post(client, b"")).status == 400
    assert (await _post(client, b"not a wav file")).status == 400
    assert (await _post(client, _wav(), "application/json")).status == 400
    assert (await _post(client, _wav(), "text/plain")).status == 400
    resp = await client.post(
        URL, params={"lang": "english!"}, data=_wav(), headers={"Content-Type": "audio/wav", **AUTH}
    )
    assert resp.status == 400
    assert "error" in await resp.json()
    assert provider.calls == []


# ---- 401 and 403 ----


async def test_token_and_origin_rules(client: TestClient, provider: FakeProvider) -> None:
    assert (await client.post(URL, data=_wav(), headers={"Content-Type": "audio/wav"})).status == 401
    wrong = {"Content-Type": "audio/wav", TOKEN_HEADER: "wrong"}
    assert (await client.post(URL, data=_wav(), headers=wrong)).status == 401
    evil = await _post(client, _wav(), Origin="https://evil.example")
    assert evil.status == 403
    assert "Access-Control-Allow-Origin" not in evil.headers
    good = await _post(client, _wav(), Origin="https://chipin.space")
    assert good.status == 200
    assert good.headers["Access-Control-Allow-Origin"] == "https://chipin.space"
    assert len(provider.calls) == 1


async def test_preflight_allows_the_context_header(client: TestClient) -> None:
    resp = await client.options(
        URL,
        headers={
            "Origin": "http://localhost:5173",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": f"content-type,{TOKEN_HEADER.lower()},{CONTEXT_HEADER.lower()}",
        },
    )
    assert resp.status == 204
    assert CONTEXT_HEADER in resp.headers["Access-Control-Allow-Headers"]


# ---- 413 ----


async def test_declared_too_large_is_413(config: BackendConfig, provider: FakeProvider, key: None) -> None:
    async with await _client(config, provider, max_bytes=1000) as c:
        assert (await _post(c, b"\0" * 1001, "audio/webm")).status == 413
        assert (await _post(c, _wav(10.0), "audio/wav")).status == 413
    assert provider.calls == []


async def test_chunked_upload_over_the_cap_is_413(
    config: BackendConfig, provider: FakeProvider, key: None
) -> None:
    async def chunks() -> AsyncIterator[bytes]:
        for _ in range(4):
            yield b"\0" * 1024

    async with await _client(config, provider, max_bytes=2048) as c:
        resp = await c.post(URL, data=chunks(), headers={"Content-Type": "audio/webm", **AUTH})
        assert resp.status == 413
    assert provider.calls == []


async def test_too_long_wav_is_413(config: BackendConfig, provider: FakeProvider, key: None) -> None:
    async with await _client(config, provider, max_audio_s=1.0) as c:
        assert (await _post(c, _wav(1.5))).status == 413


class _Stream:
    """A request body of ``total`` bytes that counts what was read from it."""

    def __init__(self, total: int) -> None:
        self.left = total
        self.read_bytes = 0

    async def read(self, n: int) -> bytes:
        size = min(n, self.left, 65536)
        self.left -= size
        self.read_bytes += size
        return b"\0" * size


class _Request:
    def __init__(self, total: int, declared: int | None) -> None:
        self.content = _Stream(total)
        self.content_length = declared


async def test_size_cap_stops_reading_at_the_cap() -> None:
    request = _Request(total=50 * 1024 * 1024, declared=None)
    assert await tr._read_capped(request, 2 * 1024 * 1024) is None  # type: ignore[arg-type]
    assert request.content.read_bytes == 2 * 1024 * 1024 + 1
    declared = _Request(total=50 * 1024 * 1024, declared=50 * 1024 * 1024)
    assert await tr._read_capped(declared, 2 * 1024 * 1024) is None  # type: ignore[arg-type]
    assert declared.content.read_bytes == 0


# ---- 429 ----


async def test_hourly_cap_is_429(config: BackendConfig, provider: FakeProvider, key: None) -> None:
    async with await _client(config, provider, hourly_audio_s=3.0) as c:
        assert (await _post(c, _wav())).status == 200  # provider says 2 s
        assert (await _post(c, _wav())).status == 200  # 2 s used, under 3
        resp = await _post(c, _wav())
        assert resp.status == 429
        assert "error" in await resp.json()
    assert len(provider.calls) == 2


def test_audio_budget_is_a_rolling_window() -> None:
    now = [0.0]
    budget = AudioBudget(10.0, window_s=3600.0, clock=lambda: now[0])
    budget.spend(6.0)
    now[0] = 1800.0
    budget.spend(4.0)
    assert budget.exhausted()
    now[0] = 3601.0
    assert budget.used() == 4.0
    assert not budget.exhausted()


# ---- 502 and 503 ----


async def test_provider_failure_is_502_without_its_text(config: BackendConfig, key: None) -> None:
    provider = FakeProvider(failing=frozenset({"openai/gpt-transcribe", "elevenlabs/scribe-v2"}))
    async with await _client(config, provider) as c:
        resp = await _post(c, _wav())
        assert resp.status == 502
        assert await resp.json() == {"error": "the transcription provider failed; try again"}


async def test_no_key_is_503_and_health_says_false(config: BackendConfig, provider: FakeProvider) -> None:
    async with await _client(config, provider) as c:
        assert (await (await c.get("/api/health")).json())["transcribe"] is False
        resp = await _post(c, _wav())
        assert resp.status == 503
        assert "OPENROUTER_API_KEY" in (await resp.json())["error"]
    assert provider.calls == []


async def test_health_says_true_with_a_key(client: TestClient) -> None:
    assert (await (await client.get("/api/health")).json())["transcribe"] is True


# ---- privacy ----


@pytest.fixture
def log_lines() -> Iterator[list[str]]:
    lines: list[str] = []
    sink = logger.add(lambda msg: lines.append(str(msg)), level="DEBUG")
    yield lines
    logger.remove(sink)


def _tree(*roots: Path) -> set[tuple[str, int]]:
    return {(str(p), p.stat().st_size) for root in roots for p in root.rglob("*") if p.is_file()}


async def test_nothing_reaches_disk_or_the_log(
    config: BackendConfig,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    key: None,
    log_lines: list[str],
) -> None:
    monkeypatch.chdir(tmp_path)
    audio = _wav(1.0)
    async with await _client(config, FakeProvider()) as c:
        before = _tree(tmp_path)
        resp = await _post(c, audio, **{CONTEXT_HEADER: "secret%20context%20words"})
        assert resp.status == 200
        assert _tree(tmp_path) == before
    text = "\n".join(log_lines)
    assert "transcribe: 200" in text
    for private in (SPOKEN, "secret context words", "fake-key-for-tests"):
        assert private not in text


# ---- the OpenRouter call itself, over a mock transport ----


def _mock_http(monkeypatch: pytest.MonkeyPatch, handler: Any) -> None:
    real = httpx.AsyncClient
    monkeypatch.setattr(
        tr.httpx, "AsyncClient", functools.partial(real, transport=httpx.MockTransport(handler))
    )


def _req() -> SttRequest:
    return SttRequest(audio=b"abc", audio_format="wav", model="m", language="en", prompt="hint", timeout_s=5)


async def test_openrouter_call_shape_and_one_retry(monkeypatch: pytest.MonkeyPatch, key: None) -> None:
    seen: list[dict[str, Any]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(json.loads(request.content))
        if len(seen) == 1:
            raise httpx.ConnectError("down")
        assert request.headers["Authorization"] == "Bearer fake-key-for-tests"
        return httpx.Response(200, json={"text": "hello", "usage": {"seconds": 3}})

    _mock_http(monkeypatch, handler)
    result = await openrouter_stt(_req())
    assert result == SttResult(text="hello", seconds=3.0)
    assert len(seen) == 2
    assert seen[1]["input_audio"] == {"data": "YWJj", "format": "wav"}
    assert (seen[1]["model"], seen[1]["language"], seen[1]["prompt"]) == ("m", "en", "hint")


async def test_openrouter_gives_up_after_one_retry(monkeypatch: pytest.MonkeyPatch, key: None) -> None:
    calls: list[int] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(1)
        raise httpx.ReadTimeout("slow")

    _mock_http(monkeypatch, handler)
    with pytest.raises(ProviderError):
        await openrouter_stt(_req())
    assert len(calls) == 2


async def test_openrouter_error_is_not_retried_or_passed_on(
    monkeypatch: pytest.MonkeyPatch, key: None
) -> None:
    calls: list[int] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(1)
        return httpx.Response(400, json={"error": {"message": "provider internals here"}})

    _mock_http(monkeypatch, handler)
    with pytest.raises(ProviderError) as info:
        await openrouter_stt(_req())
    assert info.value.status == 400
    assert "internals" not in str(info.value)
    assert len(calls) == 1


def test_shipped_config_has_a_transcribe_block() -> None:
    cfg = load_api_config().transcribe
    assert cfg.model and cfg.fallback_model and cfg.fallback_model != cfg.model
    assert cfg.max_bytes == 2 * 1024 * 1024
