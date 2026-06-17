"""Tenacity-based retry helpers (vendor HTTP calls)."""

from __future__ import annotations

import logging

import httpx
from tenacity import (
    RetryError,
    before_sleep_log,
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_chain,
    wait_fixed,
)

logger = logging.getLogger(__name__)


# Backoff 5s / 30s / 120s (laut AGENTS.md)
_BACKOFF = wait_chain(wait_fixed(5), wait_fixed(30), wait_fixed(120))


def http_retry():
    """Retry decorator for HTTP calls.

    Retries 3 times on transient network errors with backoff
    5s / 30s / 120s. HTTP 4xx (except 429) and 5xx above retry budget
    bubble up to the caller.
    """
    return retry(
        reraise=True,
        stop=stop_after_attempt(3),
        wait=_BACKOFF,
        retry=retry_if_exception_type(
            (
                httpx.TimeoutException,
                httpx.NetworkError,
                httpx.RemoteProtocolError,
            )
        ),
        before_sleep=before_sleep_log(logger, logging.WARNING),
    )


__all__ = ["RetryError", "http_retry"]
