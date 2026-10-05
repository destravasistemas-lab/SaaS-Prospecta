"""
Resolvedor único de identidade de leads — o ponto de entrada para criar leads
vindos de qualquer canal (WhatsApp, Instagram, Lead Ads, CSV) sem duplicar.

Não existe ID universal de pessoa entre canais (a Meta não expõe), então a
resolução é em cascata:
  1. external_id — o ID do canal (PSID do Instagram, número do WhatsApp),
     casando com o handle primário OU com os handles absorvidos em mesclagens
     anteriores (alt_handles);
  2. telefone — normalizado;
  3. email — case-insensitive.

Ao encontrar por telefone/email um lead de OUTRO canal, o external_id novo é
anexado em alt_handles — mensagens futuras daquele canal acham o lead
unificado direto pelo passo 1.
"""
import json
import logging
import uuid

from sqlalchemy import select, or_, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.phone import normalize_phone
from app.models.lead import Lead, LeadSource, LeadStatus
from app.services.lead_merge import (
    parse_handles, serialize_handles, auto_merge_by_phone, auto_merge_by_email,
)

logger = logging.getLogger(__name__)


async def resolve_or_create_lead(
    db: AsyncSession,
    account_id: str,
    *,
    external_id: str | None = None,
    phone: str | None = None,
    email: str | None = None,
    name: str | None = None,
    source: LeadSource = LeadSource.MANUAL,
    origin_ad_id: str | None = None,
    metadata: dict | None = None,
) -> Lead:
    """
    Localiza o lead desta pessoa pela cascata external_id → telefone → email,
    completando os campos que faltarem; se não existir, cria. Sempre retorna
    o lead unificado (nunca um duplicado).
    """
    phone = normalize_phone(phone) if phone else None
    email = email.strip().lower() if email else None

    lead: Lead | None = None

    # 1) external_id — handle primário ou absorvido em mesclagem anterior
    if external_id:
        result = await db.execute(
            select(Lead).where(
                Lead.account_id == account_id,
                or_(
                    Lead.instagram_handle == external_id,
                    Lead.alt_handles.like(f"%,{external_id},%"),
                ),
            ).limit(1)
        )
        lead = result.scalar_one_or_none()

    # 2) telefone
    if lead is None and phone:
        result = await db.execute(
            select(Lead).where(
                Lead.account_id == account_id, Lead.phone == phone
            ).order_by(Lead.captured_at.asc()).limit(1)
        )
        lead = result.scalar_one_or_none()

    # 3) email
    if lead is None and email:
        result = await db.execute(
            select(Lead).where(
                Lead.account_id == account_id, func.lower(Lead.email) == email
            ).order_by(Lead.captured_at.asc()).limit(1)
        )
        lead = result.scalar_one_or_none()

    if lead is None:
        lead = Lead(
            id=str(uuid.uuid4()),
            account_id=account_id,
            instagram_handle=external_id or phone or email or str(uuid.uuid4()),
            phone=phone,
            email=email,
            name=name or external_id or phone or email,
            source=source,
            status=LeadStatus.NEW,
            origin_ad_id=origin_ad_id,
            metadata_json=json.dumps(metadata) if metadata else None,
        )
        db.add(lead)
        await db.flush()
        logger.info(
            "Lead criado (resolvedor): %s | conta %s | origem %s",
            lead.name, account_id, source.value,
        )
    else:
        # Completa campos vazios sem sobrescrever dados existentes
        if phone and not lead.phone:
            lead.phone = phone
        if email and not lead.email:
            lead.email = email
        if name and (not lead.name or lead.name == lead.instagram_handle):
            lead.name = name
        if origin_ad_id and not lead.origin_ad_id:
            lead.origin_ad_id = origin_ad_id
        if metadata:
            try:
                merged = json.loads(lead.metadata_json) if lead.metadata_json else {}
            except (ValueError, TypeError):
                merged = {}
            for k, v in metadata.items():
                merged.setdefault(k, v)
            lead.metadata_json = json.dumps(merged)
        # Achado por telefone/email vindo de outro canal: registra o external_id
        # novo para que o passo 1 encontre este lead direto da próxima vez.
        if external_id and external_id != lead.instagram_handle:
            handles = parse_handles(lead.alt_handles)
            if external_id not in handles:
                handles.append(external_id)
                lead.alt_handles = serialize_handles(handles)
        await db.flush()

    # Rede de segurança: se o preenchimento de telefone/email revelou outro
    # duplicado, unifica agora (idempotente).
    lead = await auto_merge_by_phone(lead, db)
    lead = await auto_merge_by_email(lead, db)
    return lead
