import logging

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import async_session
from app.core.security import get_current_user_ws
from app.core.ws_manager import ws_manager

logger = logging.getLogger(__name__)
router = APIRouter(tags=["websocket"])


@router.websocket("/ws")
async def websocket_endpoint(
    ws: WebSocket,
    token: str = Query(..., description="JWT access token"),
):
    """
    WebSocket para notificações em tempo real do tenant.

    Conexão: ws://localhost:8000/ws?token=<access_token>

    Eventos emitidos pelo servidor:
      - conversation_created  → nova conversa criada
      - conversation_updated  → status/atendente atualizado
      - new_message           → nova mensagem na conversa
      - message_status_updated → status de mensagem (sent/delivered/read/failed)
    """
    # Aceita o handshake primeiro; validar antes de aceitar pode gerar
    # "got websocket.accept" se o cliente desconectar durante a checagem.
    await ws.accept()

    async with async_session() as db:
        user = await get_current_user_ws(token, db)

    if not user:
        await ws.close(code=4001, reason="Token inválido ou expirado.")
        return

    tenant_id = user.tenant_id
    await ws_manager.connect(tenant_id, ws)
    logger.info("WS autenticado: user=%s tenant=%s", user.username, tenant_id)

    try:
        while True:
            # Mantém a conexão viva; cliente pode enviar pings
            data = await ws.receive_text()
            if data == "ping":
                await ws.send_text("pong")
    except WebSocketDisconnect:
        pass
    finally:
        await ws_manager.disconnect(tenant_id, ws)
        logger.info("WS desconectado: user=%s tenant=%s", user.username, tenant_id)
