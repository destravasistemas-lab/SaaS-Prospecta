"""
Unificação de leads que representam a mesma pessoa em canais diferentes
(ex: DM do Instagram + número do WhatsApp).

Não existe um identificador em comum entre um PSID do Instagram e um número
do WhatsApp — a Meta não expõe isso. Então a ligação acontece de duas formas:
  - manual: um atendente reconhece e mescla dois leads (endpoint em leads.py);
  - automática: quando dois leads passam a ter o MESMO telefone.

Para que a mesclagem "grude" (mensagens futuras acharem o lead unificado em
vez de recriar o duplicado), guardamos os IDs externos absorvidos em
Lead.alt_handles, e _find_lead passa a casar por ele também.
"""
import json
import logging

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.lead import Lead
from app.models.conversation import Conversation

logger = logging.getLogger(__name__)


def parse_handles(raw: str | None) -> list[str]:
    return [h for h in (raw or "").split(",") if h]


def serialize_handles(handles: list[str]) -> str | None:
    # Envolto em vírgulas nas pontas para casar com LIKE '%,id,%'
    uniq = list(dict.fromkeys(h for h in handles if h))
    return "," + ",".join(uniq) + "," if uniq else None


def _looks_like_raw_id(name: str | None, handle: str) -> bool:
    """Nome 'ruim' — vazio, igual ao handle, ou só dígitos (PSID/telefone)."""
    if not name:
        return True
    return name == handle or name.replace("+", "").isdigit()


async def merge_leads(survivor: Lead, absorbed: Lead, db: AsyncSession) -> Lead:
    """
    Funde `absorbed` em `survivor`: move as conversas, completa campos vazios,
    registra os IDs externos do absorvido e apaga o duplicado. Retorna o lead
    sobrevivente.
    """
    if survivor.id == absorbed.id:
        return survivor

    # 1. Move todas as conversas do absorvido para o sobrevivente.
    await db.execute(
        update(Conversation)
        .where(Conversation.customer_id == absorbed.id)
        .values(customer_id=survivor.id)
    )

    # 2. Completa campos vazios do sobrevivente com dados do absorvido.
    if not survivor.phone and absorbed.phone:
        survivor.phone = absorbed.phone
    if not survivor.email and absorbed.email:
        survivor.email = absorbed.email
    if not survivor.ig_user_id and absorbed.ig_user_id:
        survivor.ig_user_id = absorbed.ig_user_id
    # Nome: prefere um nome "de verdade" a um PSID/telefone cru.
    if _looks_like_raw_id(survivor.name, survivor.instagram_handle) and not _looks_like_raw_id(
        absorbed.name, absorbed.instagram_handle
    ):
        survivor.name = absorbed.name

    # 3. Registra os identificadores externos do absorvido (handle + alt_handles
    #    dele) para que mensagens futuras daquele canal achem o sobrevivente.
    handles = parse_handles(survivor.alt_handles)
    handles.append(absorbed.instagram_handle)
    handles.extend(parse_handles(absorbed.alt_handles))
    # O handle primário do sobrevivente não precisa ir no alt (já casa direto)
    handles = [h for h in handles if h != survivor.instagram_handle]
    survivor.alt_handles = serialize_handles(handles)

    # 4. Preserva metadados de ambos.
    try:
        merged_meta = json.loads(survivor.metadata_json) if survivor.metadata_json else {}
        absorbed_meta = json.loads(absorbed.metadata_json) if absorbed.metadata_json else {}
        for k, v in absorbed_meta.items():
            merged_meta.setdefault(k, v)
        if merged_meta:
            survivor.metadata_json = json.dumps(merged_meta)
    except (ValueError, TypeError):
        pass

    # 5. Mantém o melhor score, se houver.
    if (absorbed.score or 0) > (survivor.score or 0):
        survivor.score = absorbed.score
        survivor.score_label = absorbed.score_label
        survivor.score_notes = absorbed.score_notes

    await db.delete(absorbed)
    await db.flush()
    logger.info("Leads mesclados: %s absorveu %s", survivor.id, absorbed.id)
    return survivor


async def _auto_merge_by_column(lead: Lead, column, value: str, db: AsyncSession) -> Lead:
    """Funde `lead` com qualquer outro da conta cujo `column` == value (mais antigo sobrevive)."""
    result = await db.execute(
        select(Lead).where(
            Lead.account_id == lead.account_id,
            column == value,
            Lead.id != lead.id,
        )
    )
    others = result.scalars().all()

    survivor = lead
    for other in others:
        if survivor.captured_at <= other.captured_at:
            survivor = await merge_leads(survivor, other, db)
        else:
            survivor = await merge_leads(other, survivor, db)
    return survivor


async def auto_merge_by_phone(lead: Lead, db: AsyncSession) -> Lead:
    """
    Se outro lead da mesma conta tiver o MESMO telefone, funde os dois
    automaticamente. Mantém o lead mais antigo como sobrevivente. Retorna o
    sobrevivente (pode ser diferente do lead recebido).
    """
    if not lead.phone:
        return lead
    return await _auto_merge_by_column(lead, Lead.phone, lead.phone, db)


async def auto_merge_by_email(lead: Lead, db: AsyncSession) -> Lead:
    """Idem auto_merge_by_phone, mas usando o email como chave de junção."""
    if not lead.email:
        return lead
    return await _auto_merge_by_column(lead, Lead.email, lead.email, db)
