"""
Cliente Redis compartilhado (debounce da IA, rate limit, dedup de webhook).
Sem REDIS_URL (ou Redis fora do ar) cai num fallback em memória — funciona
num processo único; para multi-worker use Redis (já incluído no compose).
"""
import logging
import time

from app.core.config import settings

logger = logging.getLogger(__name__)

_client = None
_memory: dict[str, tuple[str, float]] = {}  # key -> (value, expires_at)


class MemoryStore:
    """Fallback em memória com a mesma interface mínima usada no app."""

    async def incr_with_ttl(self, key: str, ttl: int) -> int:
        now = time.monotonic()
        value, exp = _memory.get(key, ("0", 0.0))
        if exp < now:
            value = "0"
        count = int(value) + 1
        _memory[key] = (str(count), now + ttl if count == 1 else (exp if exp >= now else now + ttl))
        return count

    async def set_nx_ttl(self, key: str, value: str, ttl: int) -> bool:
        now = time.monotonic()
        _, exp = _memory.get(key, ("", 0.0))
        if exp >= now:
            return False
        _memory[key] = (value, now + ttl)
        return True

    async def get(self, key: str) -> str | None:
        value, exp = _memory.get(key, (None, 0.0))
        return value if exp >= time.monotonic() else None

    async def set_ttl(self, key: str, value: str, ttl: int) -> None:
        _memory[key] = (value, time.monotonic() + ttl)


class RedisStore:
    def __init__(self, client):
        self._c = client

    async def incr_with_ttl(self, key: str, ttl: int) -> int:
        count = await self._c.incr(key)
        if count == 1:
            await self._c.expire(key, ttl)
        return int(count)

    async def set_nx_ttl(self, key: str, value: str, ttl: int) -> bool:
        return bool(await self._c.set(key, value, nx=True, ex=ttl))

    async def get(self, key: str) -> str | None:
        value = await self._c.get(key)
        return value.decode() if isinstance(value, bytes) else value

    async def set_ttl(self, key: str, value: str, ttl: int) -> None:
        await self._c.set(key, value, ex=ttl)


_store = None


async def get_store():
    """Store compartilhado (Redis se configurado; senão memória)."""
    global _client, _store
    if _store is not None:
        return _store
    if settings.redis_url:
        try:
            import redis.asyncio as aioredis
            _client = aioredis.from_url(settings.redis_url, socket_connect_timeout=2)
            await _client.ping()
            _store = RedisStore(_client)
            logger.info("Redis conectado (%s)", settings.redis_url)
            return _store
        except Exception as exc:
            logger.warning("Redis indisponível (%s) — usando fallback em memória", exc)
    _store = MemoryStore()
    return _store
