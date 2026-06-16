"""Token-bucket rate limiting per vendor.

Single-process in-memory implementation. For multi-process / multi-host
deployments, replace with a Redis-backed bucket.
"""

from __future__ import annotations

import threading
import time
from collections.abc import Iterator
from contextlib import contextmanager

_buckets: dict[str, _Bucket] = {}
_lock = threading.Lock()


class _Bucket:
    __slots__ = ("burst", "last", "rate", "tokens")

    def __init__(self, rate_per_minute: int, burst: int) -> None:
        self.rate = rate_per_minute / 60.0  # tokens per second
        self.burst = burst
        self.tokens = float(burst)
        self.last = time.monotonic()

    def take(self, n: int = 1) -> None:
        # Refill once outside the lock to avoid holding it across sleep.
        with _lock:
            now = time.monotonic()
            elapsed = now - self.last
            self.last = now
            self.tokens = min(self.burst, self.tokens + elapsed * self.rate)
            have = self.tokens
            self.tokens -= n

        if have >= n:
            return

        deficit = n - have
        wait_s = deficit / self.rate
        time.sleep(wait_s)


def _get_bucket(name: str, rate_per_minute: int, burst: int) -> _Bucket:
    with _lock:
        b = _buckets.get(name)
        if b is None:
            b = _Bucket(rate_per_minute, burst)
            _buckets[name] = b
        return b


@contextmanager
def limit(vendor: str, rate_per_minute: int, burst: int, n: int = 1) -> Iterator[None]:
    """Block until a token is available for `vendor`."""
    _get_bucket(vendor, rate_per_minute, burst).take(n)
    yield


__all__ = ["limit"]
