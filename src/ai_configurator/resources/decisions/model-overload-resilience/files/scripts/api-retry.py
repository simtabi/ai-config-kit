#!/usr/bin/env python3
"""Provider-agnostic retry helper for AI-model API calls.

Stdlib-only. Vendor into a project's ``scripts/`` (or
``src/<package>/api_retry.py``) when teammates need consistent
handling of Anthropic 529 / OpenAI 503 / generic 429.

Usage::

    from api_retry import call_with_retry, OverloadError

    response = call_with_retry(
        lambda: client.messages.create(...),
        provider="anthropic",
    )

The function detects the relevant status codes per provider,
honours ``Retry-After`` when present, applies exponential backoff
with jitter, and re-raises on the final attempt so callers can
surface a clear failure.

Drop into ``~/.claude/scripts/api-retry.py`` (the ai-configurator
init step puts it there). The corresponding rules are in the
``CLAUDE.md.model-overload-resilience.fragment`` that ships
alongside.
"""

from __future__ import annotations

import random
import time
from collections.abc import Callable
from typing import TypeVar

T = TypeVar("T")


# Per-provider status codes that mean "retry me later".
# 429 always means rate-limit; 5xx-class members are capacity.
PROVIDER_RETRY_CODES: dict[str, frozenset[int]] = {
    "anthropic": frozenset({429, 529}),
    "openai":    frozenset({429, 503}),
    "azure":     frozenset({429, 503}),
    "codex":     frozenset({429, 503}),  # routes to OpenAI backend
    "google":    frozenset({429, 503}),
    "gemini":    frozenset({429, 503}),
    "vertex":    frozenset({429, 503}),
    "cohere":    frozenset({429, 503}),
    "mistral":   frozenset({429, 503}),
    "local":     frozenset({503}),       # Ollama / vLLM / llama-server
    "generic":   frozenset({429, 503, 529}),  # union of everything
}


class OverloadError(Exception):
    """Raised on the final retry attempt of an overload-class error.

    Carries the per-attempt status code + Retry-After history so the
    caller can surface a useful failure to the user.
    """

    def __init__(
        self,
        message: str,
        *,
        attempts: list[tuple[int, float]],
        cause: BaseException | None = None,
    ) -> None:
        super().__init__(message)
        self.attempts = attempts
        self.__cause__ = cause


def call_with_retry(
    fn: Callable[[], T],
    *,
    provider: str = "generic",
    max_attempts: int = 5,
    base_delay: float = 1.0,
    cap_delay: float = 30.0,
    jitter_fraction: float = 0.25,
    on_retry: Callable[[int, float, Exception], None] | None = None,
) -> T:
    """Call ``fn`` with exponential-backoff retry on capacity errors.

    Args:
        fn: zero-arg callable that performs the API request.
        provider: key into ``PROVIDER_RETRY_CODES``. Default
            ``"generic"`` retries 429 + 503 + 529.
        max_attempts: total tries before giving up (inclusive of the
            first call).
        base_delay: starting delay in seconds; doubles each attempt.
        cap_delay: maximum delay (excluding jitter).
        jitter_fraction: random factor (0.25 = up to +25 percent jitter).
        on_retry: optional callback invoked as
            ``on_retry(attempt_idx, sleep_seconds, exc)`` between
            retries. Use for structured logging.

    Returns:
        The return value of ``fn`` on success.

    Raises:
        OverloadError: when every attempt failed with a retry-class
            status code. The original exception is chained as
            ``__cause__``.
        Exception: the original exception when the status code is
            NOT in the retry set (4xx client error, unknown 5xx).
    """
    codes = PROVIDER_RETRY_CODES.get(provider, PROVIDER_RETRY_CODES["generic"])
    history: list[tuple[int, float]] = []

    for attempt in range(max_attempts):
        try:
            return fn()
        except Exception as exc:
            status = _extract_status(exc)
            if status is None or status not in codes:
                raise
            history.append((status, time.time()))
            if attempt == max_attempts - 1:
                raise OverloadError(
                    f"{provider}: exhausted {max_attempts} retries on "
                    f"{[s for s, _ in history]}",
                    attempts=history,
                    cause=exc,
                ) from exc

            retry_after = _extract_retry_after(exc)
            if retry_after is not None:
                sleep = retry_after
            else:
                sleep = min(cap_delay, base_delay * (2 ** attempt))
            sleep += random.uniform(0, sleep * jitter_fraction)

            if on_retry is not None:
                on_retry(attempt, sleep, exc)
            time.sleep(sleep)

    # Unreachable: the loop always either returns or raises.
    raise OverloadError(  # pragma: no cover
        f"{provider}: retry loop exited without return",
        attempts=history,
    )


def _extract_status(exc: BaseException) -> int | None:
    """Best-effort: pull an HTTP status code off the exception.

    Matches the conventions used by anthropic, openai, google-ai,
    cohere, and the generic ``requests``/``httpx`` shape.
    """
    code = getattr(exc, "status_code", None)
    if isinstance(code, int):
        return code
    # openai / httpx style: exc.response.status_code
    resp = getattr(exc, "response", None)
    if resp is not None:
        code = getattr(resp, "status_code", None)
        if isinstance(code, int):
            return code
        code = getattr(resp, "status", None)  # some clients use .status
        if isinstance(code, int):
            return code
    return None


def _extract_retry_after(exc: BaseException) -> float | None:
    """Pull a ``Retry-After`` header off the exception, if present.

    Accepts either a delta-seconds integer/float or an HTTP-date
    string (RFC 7231). Returns ``None`` when absent or unparseable.
    """
    resp = getattr(exc, "response", None)
    if resp is None:
        return None
    headers = getattr(resp, "headers", None)
    if not headers:
        return None
    raw = headers.get("Retry-After") or headers.get("retry-after")
    if raw is None:
        return None
    # Delta-seconds form
    try:
        return float(raw)
    except (TypeError, ValueError):
        pass
    # HTTP-date form: parse via email.utils (stdlib).
    try:
        from email.utils import parsedate_to_datetime
        target = parsedate_to_datetime(raw)
        from datetime import datetime, timezone
        now = datetime.now(timezone.utc)
        if target.tzinfo is None:
            target = target.replace(tzinfo=timezone.utc)
        delta = (target - now).total_seconds()
        return max(0.0, delta)
    except (TypeError, ValueError, IndexError):
        return None


if __name__ == "__main__":
    # Tiny self-test: mock failures + a finally success.
    class _MockError(Exception):
        def __init__(self, code: int, retry_after: str | None = None) -> None:
            super().__init__(f"mock {code}")
            self.status_code = code
            self.response = type(
                "R", (), {"status_code": code, "headers": {}}
            )()
            if retry_after is not None:
                self.response.headers = {"Retry-After": retry_after}

    attempts: list[int] = []

    def flaky() -> str:
        attempts.append(1)
        if len(attempts) < 3:
            raise _MockError(529)
        return "ok"

    result = call_with_retry(
        flaky,
        provider="anthropic",
        max_attempts=5,
        base_delay=0.01,
        cap_delay=0.05,
    )
    assert result == "ok", result
    assert len(attempts) == 3, attempts
    print("self-test ok:", result, "after", len(attempts), "attempts")
