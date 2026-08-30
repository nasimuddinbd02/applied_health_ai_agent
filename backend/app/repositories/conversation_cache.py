"""Hot conversation history in Redis (design doc §12).

The agent needs the last few turns on every message. Reading them from Redis
keeps the hot path off the database, but the cache is never authoritative: a
miss (cold key, evicted key, Redis down) falls through to the repository, which
is the real record. So losing Redis costs latency, not conversations.
"""

import json
import logging

from app.core.config import Settings
from app.messaging.redis_client import RedisClient

log = logging.getLogger(__name__)


class ConversationCache:
    def __init__(self, redis: RedisClient, settings: Settings) -> None:
        self._redis = redis
        self._settings = settings

    def _key(self, conversation_id: str) -> str:
        return self._settings.key("conv", conversation_id, "turns")

    async def recent(self, conversation_id: str) -> list[dict] | None:
        """Cached turns, or None on a miss — the caller then reads the database."""
        if not self._redis.available:
            return None
        try:
            raw = await self._redis.client().lrange(self._key(conversation_id), 0, -1)
        except Exception:  # noqa: BLE001
            log.debug("Conversation cache read failed for %s", conversation_id, exc_info=True)
            return None
        if not raw:
            return None
        turns = []
        for item in raw:
            try:
                turns.append(json.loads(item))
            except json.JSONDecodeError:
                return None  # corrupt entry: treat the whole key as a miss
        return turns

    async def append(self, conversation_id: str, turn: dict) -> None:
        if not self._redis.available:
            return
        try:
            key = self._key(conversation_id)
            pipe = self._redis.client().pipeline()
            pipe.rpush(key, json.dumps(turn, default=str))
            # Keep only what the agent is given as context, so the key cannot
            # grow without bound on a long conversation.
            pipe.ltrim(key, -self._settings.conversation_history_turns, -1)
            pipe.expire(key, self._settings.conversation_cache_ttl_seconds)
            await pipe.execute()
        except Exception:  # noqa: BLE001
            log.debug("Conversation cache write failed for %s", conversation_id, exc_info=True)

    async def prime(self, conversation_id: str, turns: list[dict]) -> None:
        """Refill the key from the durable record after a miss."""
        if not self._redis.available or not turns:
            return
        try:
            key = self._key(conversation_id)
            pipe = self._redis.client().pipeline()
            pipe.delete(key)
            pipe.rpush(key, *[json.dumps(t, default=str) for t in turns])
            pipe.expire(key, self._settings.conversation_cache_ttl_seconds)
            await pipe.execute()
        except Exception:  # noqa: BLE001
            log.debug("Conversation cache prime failed for %s", conversation_id, exc_info=True)

    async def clear(self, conversation_id: str) -> None:
        if not self._redis.available:
            return
        try:
            await self._redis.client().delete(self._key(conversation_id))
        except Exception:  # noqa: BLE001
            pass
