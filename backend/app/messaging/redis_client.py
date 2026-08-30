"""Redis connection holder.

One lazily-connected async client shared by every Redis-backed collaborator
(session registry, event bus, realtime pub/sub, idempotency, rate limiting).

Redis is **coordination infrastructure, not the source of truth**: if it is
unavailable the application must still serve a single instance rather than
fall over (design doc §24, "Redis unavailable → degrade gracefully"). So the
client exposes ``available`` and never raises on connect failure — callers
degrade to their in-process fallback.
"""

import logging

from app.core.config import Settings

log = logging.getLogger(__name__)


class RedisUnavailable(RuntimeError):
    """Raised when a caller demands a client and Redis is not connected."""


class RedisClient:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._client = None
        self._available = False

    @property
    def available(self) -> bool:
        return self._available

    @property
    def url(self) -> str:
        return self._settings.redis_url

    def client(self):
        """The live ``redis.asyncio.Redis``. Raises if Redis is not connected."""
        if not self._available or self._client is None:
            raise RedisUnavailable("Redis is not connected.")
        return self._client

    async def connect(self) -> bool:
        """Open the pool and PING. Returns True when Redis is usable."""
        if not self._settings.redis_enabled:
            log.warning("Redis disabled by configuration — running single-instance.")
            self._available = False
            return False
        try:
            from redis.asyncio import Redis

            self._client = Redis.from_url(
                self._settings.redis_url,
                decode_responses=True,
                socket_timeout=5,
                socket_connect_timeout=3,
                health_check_interval=30,
            )
            await self._client.ping()
            self._available = True
            log.info("Redis connected at %s", self._settings.redis_url)
        except Exception as err:  # noqa: BLE001 — degrade, never crash startup
            self._available = False
            self._client = None
            log.warning("Redis unavailable (%s) — degrading to single-instance mode.", err)
        return self._available

    async def ping(self) -> bool:
        if self._client is None:
            return False
        try:
            await self._client.ping()
            self._available = True
        except Exception:  # noqa: BLE001
            self._available = False
        return self._available

    async def close(self) -> None:
        if self._client is not None:
            try:
                await self._client.aclose()
            except Exception:  # noqa: BLE001
                pass
        self._client = None
        self._available = False
