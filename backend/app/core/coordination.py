"""Redis-backed idempotency and rate limiting (design doc §15, §16).

Both are pure coordination concerns: they need to be shared across instances
(a client that reconnects to a different pod must not get a second booking, and
must not get a fresh rate-limit budget), and neither is worth persisting.

Both degrade to a process-local implementation when Redis is unavailable, so a
single-instance deployment keeps its guarantees and a cluster loses only the
cross-instance part — never the whole feature.
"""

import logging
import time

from app.core.config import Settings
from app.messaging.redis_client import RedisClient

log = logging.getLogger(__name__)


class IdempotencyGuard:
    """First-writer-wins claim on a key.

    ``claim`` returns True exactly once per key within the TTL. A reconnect,
    a browser refresh, a retried request or a redelivered event all replay the
    same key and get False, so the state-changing work runs once.
    """

    def __init__(self, redis: RedisClient, settings: Settings) -> None:
        self._redis = redis
        self._settings = settings
        self._local: dict[str, float] = {}

    def _key(self, scope: str, key: str) -> str:
        return self._settings.key("idem", scope, key)

    async def claim(self, scope: str, key: str, *, ttl: int | None = None) -> bool:
        ttl = ttl or self._settings.idempotency_ttl_seconds
        full = self._key(scope, key)
        if self._redis.available:
            try:
                return bool(await self._redis.client().set(full, "1", nx=True, ex=ttl))
            except Exception:  # noqa: BLE001
                log.debug("Idempotency claim via Redis failed for %s", full, exc_info=True)
        return self._claim_local(full, ttl)

    def _claim_local(self, full: str, ttl: int) -> bool:
        now = time.time()
        # Opportunistic sweep — this map only ever holds keys seen by this
        # process, so it stays small.
        for expired in [k for k, exp in self._local.items() if exp <= now]:
            self._local.pop(expired, None)
        if full in self._local:
            return False
        self._local[full] = now + ttl
        return True

    async def release(self, scope: str, key: str) -> None:
        """Give a key back after the guarded work failed, so a retry can run."""
        full = self._key(scope, key)
        self._local.pop(full, None)
        if self._redis.available:
            try:
                await self._redis.client().delete(full)
            except Exception:  # noqa: BLE001
                pass


class RateLimiter:
    """Fixed-window counter, keyed by chat session.

    Fixed windows (rather than a sliding log) keep this to one INCR + one
    EXPIRE per message, which is what you want on the hot path of a chat
    gateway.
    """

    def __init__(self, redis: RedisClient, settings: Settings) -> None:
        self._redis = redis
        self._settings = settings
        self._local: dict[str, tuple[int, float]] = {}

    def _key(self, scope: str, subject: str, window_start: int) -> str:
        return self._settings.key("rl", scope, subject, str(window_start))

    async def allow(self, scope: str, subject: str, *, limit: int | None = None,
                    window: int | None = None) -> bool:
        limit = limit or self._settings.chat_rate_limit_messages
        window = window or self._settings.chat_rate_limit_window_seconds
        window_start = int(time.time()) // window
        key = self._key(scope, subject, window_start)

        if self._redis.available:
            try:
                client = self._redis.client()
                pipe = client.pipeline()
                pipe.incr(key)
                pipe.expire(key, window)
                count, _ = await pipe.execute()
                return int(count) <= limit
            except Exception:  # noqa: BLE001
                log.debug("Rate-limit check via Redis failed for %s", key, exc_info=True)

        count, expires_at = self._local.get(key, (0, time.time() + window))
        count += 1
        self._local[key] = (count, expires_at)
        now = time.time()
        for stale in [k for k, (_, exp) in self._local.items() if exp <= now]:
            self._local.pop(stale, None)
        return count <= limit
