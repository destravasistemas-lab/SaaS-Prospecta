import asyncio
import json
import logging
from collections import defaultdict
from typing import Any

from fastapi import WebSocket

logger = logging.getLogger(__name__)


class ConnectionManager:
    """Keeps track of active WebSocket connections grouped by tenant_id."""

    def __init__(self):
        # tenant_id -> set of active WebSocket connections
        self._connections: dict[str, set[WebSocket]] = defaultdict(set)
        self._lock = asyncio.Lock()

    async def connect(self, tenant_id: str, ws: WebSocket) -> None:
        # O handshake (ws.accept) é feito pelo endpoint antes de validar o token.
        async with self._lock:
            self._connections[tenant_id].add(ws)
        logger.info("WS connected: tenant=%s total=%d", tenant_id, len(self._connections[tenant_id]))

    async def disconnect(self, tenant_id: str, ws: WebSocket) -> None:
        async with self._lock:
            self._connections[tenant_id].discard(ws)
            if not self._connections[tenant_id]:
                del self._connections[tenant_id]
        logger.info("WS disconnected: tenant=%s", tenant_id)

    async def broadcast(self, tenant_id: str, event_type: str, data: Any) -> None:
        """Sends a JSON message to every connection in the tenant."""
        message = json.dumps({"event": event_type, "data": data}, default=str)
        dead: list[WebSocket] = []
        for ws in list(self._connections.get(tenant_id, set())):
            try:
                await ws.send_text(message)
            except Exception:
                dead.append(ws)
        for ws in dead:
            await self.disconnect(tenant_id, ws)

    def active_count(self, tenant_id: str) -> int:
        return len(self._connections.get(tenant_id, set()))


# Singleton — imported wherever broadcast is needed
ws_manager = ConnectionManager()
