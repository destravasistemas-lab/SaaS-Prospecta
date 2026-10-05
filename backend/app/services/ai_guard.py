"""
Proteções da IA: anti-loop IA↔bot e rate limit por remetente.

Se detectado padrão de bot na mensagem recebida: NÃO responder, logar.
Rate limit: máx N mensagens/min por sender (default 20) — acima disso a IA
ignora (o webhook continua salvando as mensagens normalmente).
"""
import logging
import re

from app.core.redis import get_store

logger = logging.getLogger(__name__)

# Padrões típicos de resposta automática/bot na MENSAGEM recebida
_BOT_PATTERNS = re.compile(
    r"(auto[- ]?reply|resposta autom[aá]tica|out of office|fora do escrit[oó]rio"
    r"|do[- ]?not[- ]?reply|n[aã]o responda|this is an automated|mensagem autom[aá]tica"
    r"|\bbot\b)",
    re.IGNORECASE,
)


def looks_like_bot(text: str | None, payload: dict | None = None) -> bool:
    """Heurísticas anti-loop sobre a mensagem recebida."""
    if payload:
        # Header/flag explícita de bot no payload do webhook
        if str(payload.get("X-Bot", payload.get("x-bot", ""))).lower() == "true":
            return True
        # Mensagens de sistema/notificação da própria plataforma
        if payload.get("type") == "system":
            return True
    if text and _BOT_PATTERNS.search(text):
        return True
    return False


async def sender_rate_limited(tenant_id: str, sender: str, limit_per_min: int = 20) -> bool:
    """True se o remetente estourou o limite de mensagens/minuto (anti-flood/loop)."""
    store = await get_store()
    count = await store.incr_with_ttl(f"ai:rl:{tenant_id}:{sender}", ttl=60)
    if count > limit_per_min:
        logger.warning("Anti-loop: sender %s do tenant %s estourou %d msg/min — IA silenciada",
                       sender, tenant_id, limit_per_min)
        return True
    return False


async def dedupe_message(message_id: str) -> bool:
    """
    Idempotência do webhook: True se esta message_id JÁ foi processada
    (a Meta reenvia webhooks). Marca por 24h.
    """
    if not message_id:
        return False
    store = await get_store()
    fresh = await store.set_nx_ttl(f"wh:dedup:{message_id}", "1", ttl=86400)
    return not fresh
