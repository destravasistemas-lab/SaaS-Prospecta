"""
Cria/atualiza a automação de comentário escopada a um post do Instagram, no
momento em que o post é publicado (o media_id só existe após publicar).

Chamado a partir do publish imediato, do publish-now e do scheduler.
"""
import logging

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.automation import AutomationConfig

logger = logging.getLogger(__name__)


async def create_post_automation(
    db: AsyncSession,
    account_id: str,
    media_id: str | None,
    keyword: str | None,
    comment_reply: str | None,
    dm_message: str | None,
    link_message: str | None,
) -> AutomationConfig | None:
    """
    Se houver palavra-chave, cria uma automação de comentário ligada a este
    post. Regras do fluxo (conforme definido pelo usuário):
      - com 2ª mensagem (link): coment. → 1ª DM → resposta → 2ª DM (link) → humano
      - sem 2ª mensagem: dispara o comentário uma vez → passa direto para humano
    O handoff é sempre ligado (é o fim do fluxo do bot deste post).
    """
    if not keyword or not media_id:
        return None

    # Evita duplicar se o mesmo post for reprocessado
    existing = await db.execute(
        select(AutomationConfig).where(
            AutomationConfig.account_id == account_id,
            AutomationConfig.media_id == media_id,
            AutomationConfig.keyword == keyword,
        )
    )
    if existing.scalar_one_or_none():
        return None

    config = AutomationConfig(
        account_id=account_id,
        keyword=keyword,
        trigger_type="comment",
        media_id=media_id,
        auto_reply_message=dm_message or comment_reply or keyword,
        comment_reply_message=comment_reply,
        dm_message=dm_message,
        link_message=link_message or None,
        handoff_to_human=True,
        is_active=True,
    )
    db.add(config)
    await db.flush()
    logger.info("Automação do post criada: media=%s keyword=%s handoff=on", media_id, keyword)
    return config
