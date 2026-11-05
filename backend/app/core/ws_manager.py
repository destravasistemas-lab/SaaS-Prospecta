import asyncio
import json
import logging
import uuid
from collections import defaultdict
from typing import Any

from fastapi import WebSocket

from app.core.config import settings
from app.core.redis import get_redis_client, get_store

logger = logging.getLogger(__name__)

_FANOUT_CHANNEL = "ws:events"
_PRESENCE_TTL = 60  # o cliente envia ping a cada 25 s


class ConnectionManager:
    """Keeps track of active WebSocket connections grouped by tenant_id."""

    def __init__(self):
        # tenant_id -> set of active WebSocket connections
        self._connections: dict[str, set[WebSocket]] = defaultdict(set)
        self._users: dict[WebSocket, str] = {}
        self._lock = asyncio.Lock()
        self._instance_id = uuid.uuid4().hex

    async def connect(self, tenant_id: str, ws: WebSocket, user_id: str | None = None) -> None:
        # O handshake (ws.accept) é feito pelo endpoint antes de validar o token.
        async with self._lock:
            self._connections[tenant_id].add(ws)
            if user_id:
                self._users[ws] = user_id
        logger.info("WS connected: tenant=%s total=%d", tenant_id, len(self._connections[tenant_id]))

    async def disconnect(self, tenant_id: str, ws: WebSocket) -> None:
        async with self._lock:
            self._connections[tenant_id].discard(ws)
            self._users.pop(ws, None)
            if not self._connections[tenant_id]:
                del self._connections[tenant_id]
        logger.info("WS disconnected: tenant=%s", tenant_id)

    async def broadcast(self, tenant_id: str, event_type: str, data: Any) -> None:
        """Sends a JSON message to every connection in the tenant."""
        message = json.dumps({"event": event_type, "data": data}, default=str)
        await self._deliver(tenant_id, message)
        await self._publish(tenant_id, message)

    async def send_to_users(self, tenant_id: str, user_ids: list[str], event_type: str, data: Any) -> None:
        """Sends a JSON message only to these users' connections in the tenant."""
        if not user_ids:
            return
        message = json.dumps({"event": event_type, "data": data}, default=str)
        await self._deliver(tenant_id, message, set(user_ids))
        await self._publish(tenant_id, message, user_ids)

    async def _deliver(self, tenant_id: str, message: str, user_ids: set[str] | None = None) -> None:
        dead: list[WebSocket] = []
        for ws in list(self._connections.get(tenant_id, set())):
            if user_ids is not None and self._users.get(ws) not in user_ids:
                continue
            try:
                await ws.send_text(message)
            except Exception:
                dead.append(ws)
        for ws in dead:
            await self.disconnect(tenant_id, ws)

    def active_count(self, tenant_id: str) -> int:
        return len(self._connections.get(tenant_id, set()))

    async def touch_presence(self, user_id: str) -> None:
        store = await get_store()
        await store.set_ttl(f"ws:online:{user_id}", "1", ttl=_PRESENCE_TTL)

    async def is_online(self, user_id: str) -> bool:
        store = await get_store()
        return await store.get(f"ws:online:{user_id}") is not None

    async def _publish(self, tenant_id: str, message: str, user_ids: list[str] | None = None) -> None:
        """A entrega local já aconteceu: se o Redis falhar, só as outras instâncias perdem o evento."""
        if not settings.ws_redis_fanout:
            return
        try:
            client = await get_redis_client()
            if client:
                await client.publish(_FANOUT_CHANNEL, json.dumps({
                    "origin": self._instance_id, "tenant_id": tenant_id,
                    "user_ids": user_ids, "message": message,
                }))
        except Exception as exc:
            logger.warning("WS fan-out: falha ao publicar (%s)", type(exc).__name__)

    async def _on_fanout(self, raw: bytes | str) -> None:
        envelope = json.loads(raw)
        if envelope.get("origin") == self._instance_id:
            return
        user_ids = envelope.get("user_ids")
        await self._deliver(
            envelope["tenant_id"], envelope["message"], set(user_ids) if user_ids is not None else None,
        )

    async def fanout_loop(self) -> None:
        """Recebe os eventos publicados pelas outras instâncias e reconecta se o Redis cair."""
        while True:
            try:
                client = await get_redis_client()
                if not client:
                    logger.warning("WS_REDIS_FANOUT ligado sem Redis: eventos ficam só nesta instância")
                    return
                pubsub = client.pubsub()
                await pubsub.subscribe(_FANOUT_CHANNEL)
                async for item in pubsub.listen():
                    if item.get("type") == "message":
                        await self._on_fanout(item["data"])
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                logger.warning("WS fan-out: conexão perdida (%s)", type(exc).__name__)
            await asyncio.sleep(2)


# Singleton — imported wherever broadcast is needed
ws_manager = ConnectionManager()
