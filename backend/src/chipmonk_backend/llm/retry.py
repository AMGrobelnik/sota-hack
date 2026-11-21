"""Retry for paid calls: transient faults only, same model, bounded.

Policy (from AI Inventor's paid-lane retry): retry HTTP
:data:`TRANSIENT_STATUSES` and connection failures, back off 1, 2, 4, 8 s
(honouring ``Retry-After``), and re-raise the ORIGINAL error when attempts run
out or the error is not transient. A read timeout is not retried: the provider
may already be generating, and billing, the answer.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime
from typing import Any

import httpx
from loguru import logger
from tenacity import AsyncRetrying, RetryCallState, retry_if_exception, stop_after_attempt

TRANSIENT_STATUSES: frozenset[int] = frozenset({429, 500, 502, 503, 504, 524})
BACKOFF_S: tuple[float, ...] = (1.0, 2.0, 4.0, 8.0)

#: Longest ``Retry-After`` honoured; a longer hint is a quota reset, not a blip.
RETRY_AFTER_CAP_S = 60.0

#: Failures where the request never reached the provider (or the connection
#: dropped before an answer started).
_CONNECTION_ERRORS: tuple[type[Exception], ...] = (
    httpx.ConnectError,
    httpx.ConnectTimeout,
    httpx.PoolTimeout,
    httpx.ReadError,
    httpx.WriteError,
    httpx.RemoteProtocolError,
)


def _status_of(err: BaseException) -> int | None:
    """The HTTP status an error carries: httpx's ``response`` or a ``status_code`` field."""
    response = getattr(err, "response", None)
    status = getattr(response, "status_code", None) or getattr(err, "status_code", None)
    return status if isinstance(status, int) else None


def _retry_after_s(err: BaseException) -> float | None:
    """Seconds from a ``Retry-After`` header (delta or HTTP date), capped; else ``None``."""
    headers: Any = getattr(getattr(err, "response", None), "headers", None)
    raw = headers.get("retry-after") if headers is not None else None
    if not raw:
        return None
    try:
        seconds = float(raw)
    except ValueError:
        try:
            when = parsedate_to_datetime(raw)
        except (TypeError, ValueError):
            return None
        seconds = (when - datetime.now(UTC)).total_seconds()
    return min(max(seconds, 0.0), RETRY_AFTER_CAP_S)


def is_retryable(err: BaseException) -> tuple[bool, float | None]:
    """``(retry?, retry_after_s)`` for an exception from a paid HTTP call.

    ``retry_after_s`` is the provider's own ``Retry-After`` hint when it sent
    one, else ``None`` (the caller then uses :data:`BACKOFF_S`).
    """
    if isinstance(err, _CONNECTION_ERRORS):
        return True, None
    if _status_of(err) in TRANSIENT_STATUSES:
        return True, _retry_after_s(err)
    return False, None


def _wait(state: RetryCallState) -> float:
    """The provider's ``Retry-After`` if given, else the next step of :data:`BACKOFF_S`."""
    err = state.outcome.exception() if state.outcome is not None else None
    hint = is_retryable(err)[1] if err is not None else None
    if hint is not None:
        return hint
    return BACKOFF_S[min(state.attempt_number - 1, len(BACKOFF_S) - 1)]


def _log_retry(state: RetryCallState) -> None:
    err = state.outcome.exception() if state.outcome is not None else None
    wait_s = state.next_action.sleep if state.next_action is not None else 0.0
    logger.warning(
        "paid call: transient error ({}) on attempt {}; retrying in {:.1f}s",
        type(err).__name__,
        state.attempt_number,
        wait_s,
    )


async def retry_paid_call[T](call: Callable[[], Awaitable[T]], *, attempts: int) -> T:
    """Await ``call()`` up to ``attempts`` times under the policy above.

    A non-transient error, and the last transient one, propagate unchanged.
    """
    retrying = AsyncRetrying(
        retry=retry_if_exception(lambda err: is_retryable(err)[0]),
        stop=stop_after_attempt(max(attempts, 1)),
        wait=_wait,
        before_sleep=_log_retry,
        reraise=True,
    )
    return await retrying(call)


__all__ = ["BACKOFF_S", "TRANSIENT_STATUSES", "is_retryable", "retry_paid_call"]
