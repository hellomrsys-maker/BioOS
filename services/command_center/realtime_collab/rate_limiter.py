"""Simple per‑user token‑bucket rate limiter.

The limiter is instantiated once (module‑level) and maintains a dictionary of
``TokenBucket`` objects keyed by user id.  Each bucket refills at ``rate`` tokens
per second up to ``capacity``.  The ``allow_op`` function returns ``True`` when
the user may perform an operation, ``False`` otherwise.
"""

from __future__ import annotations

import time
from collections import defaultdict
from dataclasses import dataclass


@dataclass
class TokenBucket:
    rate: float          # tokens added per second
    capacity: int        # maximum burst size
    tokens: float = 0.0
    timestamp: float = 0.0

    def __post_init__(self):
        self.tokens = self.capacity
        self.timestamp = time.time()

    def consume(self, n: int = 1) -> bool:
        now = time.time()
        # Refill based on elapsed time.
        elapsed = now - self.timestamp
        self.tokens = min(self.capacity, self.tokens + elapsed * self.rate)
        self.timestamp = now
        if self.tokens >= n:
            self.tokens -= n
            return True
        return False


# Global stores – in a real deployment you might back these with Redis.
# Regular CRDT operation bucket: 20 ops per 5 seconds (4 ops/sec) with burst 40.
_op_buckets: defaultdict[str, TokenBucket] = defaultdict(
    lambda: TokenBucket(rate=20 / 5, capacity=40)
)
# Presence (cursor) bucket: up to 30 updates per second, burst 30.
_presence_buckets: defaultdict[str, TokenBucket] = defaultdict(
    lambda: TokenBucket(rate=30.0, capacity=30)
)


def allow_op(user_id: str) -> bool:
    """Return ``True`` if the user may issue another CRDT operation now."""
    bucket = _op_buckets[user_id]
    return bucket.consume()


def allow_presence(user_id: str) -> bool:
    """Return ``True`` if the user may send another presence update now."""
    bucket = _presence_buckets[user_id]
    return bucket.consume()