"""In-memory sliding window rate limiter for per-tenant and per-client throughput throttling.

NOTE ON SCOPE:
This rate limiter is explicitly single-node in-memory (storing sliding timestamp queues
in application memory without requiring an external Redis instance), consistent with TraceMind's
zero-external-cache architecture. In a distributed multi-node deployment, rate limits apply
per gateway node or can be backed by a distributed key-value store.
"""

from __future__ import annotations

import asyncio
import time
from collections import defaultdict, deque
from typing import NamedTuple


class RateLimitResult(NamedTuple):
    """Result of a rate limit evaluation."""

    allowed: bool
    limit: int
    remaining: int
    reset_seconds: int
    retry_after: int


class InMemorySlidingWindowRateLimiter:
    """Sliding-window timestamp rate limiter maintaining exact request history per key."""

    def __init__(self, default_rate_per_minute: int = 1200) -> None:
        self.default_rate_per_minute = default_rate_per_minute
        self._windows: dict[str, deque[float]] = defaultdict(deque)
        self._lock = asyncio.Lock()

    async def check(
        self,
        key: str,
        max_requests: int | None = None,
        window_seconds: int = 60,
    ) -> RateLimitResult:
        """Evaluate whether a request identified by `key` is allowed under the rate limit.

        Args:
            key: Rate limit key (e.g. `tenant:<tenant_id>` or `ip:<client_ip>`)
            max_requests: Maximum allowed requests within the window (defaults to `default_rate_per_minute`)
            window_seconds: Duration of the sliding window in seconds (default 60s)

        Returns:
            RateLimitResult containing allowed flag, remaining count, and retry after seconds.
        """

        limit = max_requests if max_requests is not None else self.default_rate_per_minute
        now = time.monotonic()
        cutoff = now - window_seconds

        async with self._lock:
            queue = self._windows[key]

            # Evict timestamps older than the sliding window cutoff
            while queue and queue[0] < cutoff:
                queue.popleft()

            current_count = len(queue)

            if current_count >= limit:
                # Calculate time until the oldest request falls outside the window
                oldest = queue[0]
                retry_after = max(1, int(window_seconds - (now - oldest)))
                return RateLimitResult(
                    allowed=False,
                    limit=limit,
                    remaining=0,
                    reset_seconds=retry_after,
                    retry_after=retry_after,
                )

            # Record this request timestamp
            queue.append(now)
            remaining = max(0, limit - (current_count + 1))
            return RateLimitResult(
                allowed=True,
                limit=limit,
                remaining=remaining,
                reset_seconds=window_seconds,
                retry_after=0,
            )

    async def reset(self, key: str | None = None) -> None:
        """Reset rate limit history for a specific key or all keys."""
        async with self._lock:
            if key is not None:
                self._windows.pop(key, None)
            else:
                self._windows.clear()

    def clear(self, key: str | None = None) -> None:
        """Synchronously clear rate limit history for a key or all keys."""
        if key is not None:
            self._windows.pop(key, None)
        else:
            self._windows.clear()


# Global in-memory rate limiter singleton
_rate_limiter: InMemorySlidingWindowRateLimiter | None = None


def get_rate_limiter() -> InMemorySlidingWindowRateLimiter:
    """Retrieve global sliding window rate limiter singleton."""
    global _rate_limiter
    if _rate_limiter is None:
        _rate_limiter = InMemorySlidingWindowRateLimiter()
    return _rate_limiter
