"""Retry for paid calls: transient faults only, same model, bounded.

Policy (AI Inventor ``sdk_openhands_agent/paid_retry.py``): retry HTTP
:data:`TRANSIENT_STATUSES` and connection resets, back off 1, 2, 4, 8 s
(honouring ``Retry-After``), re-raise the ORIGINAL error when attempts run out
or the error is not transient. Never retry a call the provider may already
have billed for without the caller's say-so. Build it on ``tenacity`` with
``reraise=True``. Leave out the Flex-offline wait, which belonged to AI
Inventor's metering proxy.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable

TRANSIENT_STATUSES: frozenset[int] = frozenset({429, 500, 502, 503, 504, 524})
BACKOFF_S: tuple[float, ...] = (1.0, 2.0, 4.0, 8.0)


def is_retryable(err: BaseException) -> tuple[bool, float | None]:
    """``(retry?, retry_after_s)`` for an exception from a paid HTTP call."""
    raise NotImplementedError("port paid_retry.paid_retryable for httpx errors")


async def retry_paid_call[T](call: Callable[[], Awaitable[T]], *, attempts: int) -> T:
    """Await ``call()`` up to ``attempts`` times under the policy above."""
    raise NotImplementedError("port paid_retry.retry_paid_call (async, tenacity)")


__all__ = ["BACKOFF_S", "TRANSIENT_STATUSES", "is_retryable", "retry_paid_call"]
