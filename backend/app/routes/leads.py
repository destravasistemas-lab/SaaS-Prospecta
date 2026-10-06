import csv
import io
import logging
from datetime import datetime, timezone
from typing import List, Optional

from fastapi import APIRouter, HTTPException, Depends, Query, UploadFile, File
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.database import get_db
from app.core.security import get_current_user
from app.core.phone import normalize_phone
from app.models.user import User
from app.models.lead import Lead, LeadSource, LeadStatus
from app.schemas import LeadResponse, LeadUpdate, LeadConsentUpdate
from app.services.lead_scoring import score_lead
from app.services.lead_merge import merge_leads, auto_merge_by_phone, auto_merge_by_email

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/leads", tags=["leads"])


class DMSendRequest(BaseModel):
    lead_id: str
    message: str


class MergeLeadsRequest(BaseModel):
    absorbed_lead_id: str  # lead que será fundido e removido


_NAME_COLS = {"nome", "name", "cliente", "contato", "nome completo"}
_PHONE_COLS = {"telefone", "phone", "celular", "whatsapp", "numero", "número", "fone", "tel"}
_OPTIN_COLS = {"opt_in", "optin", "opt-in", "consent", "consentimento", "whatsapp_opt_in"}
_TRUTHY = {"1", "true", "sim", "yes", "s", "y", "x"}


@router.post("/import")
async def import_leads_csv(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Importa leads em massa de um CSV com colunas de nome e telefone.
    Telefones são padronizados para 55DDDNUMERO; duplicados/ inválidos são pulados.
    Coluna opcional `opt_in` (sim/yes/1) registra o consentimento para WhatsApp.
    """
    if current_user.role != "admin":
        raise HTTPException(403, "Apenas admins podem importar leads.")

    content = await file.read()
    try:
        text = content.decode("utf-8-sig")
    except UnicodeDecodeError:
        text = content.decode("latin-1")

    # Detecta o delimitador (vírgula ou ponto-e-vírgula)
    sample = text[:2000]
    delimiter = ";" if sample.count(";") > sample.count(",") else ","
    reader = csv.DictReader(io.StringIO(text), delimiter=delimiter)

    def find_col(fieldnames, options: set[str]) -> str | None:
        for f in fieldnames or []:
            if f and f.strip().lower() in options:
                return f
        return None

    name_col = find_col(reader.fieldnames, _NAME_COLS)
    phone_col = find_col(reader.fieldnames, _PHONE_COLS)
    optin_col = find_col(reader.fieldnames, _OPTIN_COLS)
    now = datetime.now(timezone.utc)
    if not phone_col:
        raise HTTPException(
            400,
            "O CSV precisa de uma coluna de telefone (ex.: cabeçalho 'nome,telefone').",
        )

    # Telefones já existentes (para não duplicar)
    existing = await db.execute(
        select(Lead.phone).where(
            Lead.account_id == current_user.tenant_id, Lead.phone.isnot(None)
        )
    )
    seen = {row[0] for row in existing.all()}

    created = skipped = invalid = 0
    for row in reader:
        phone = normalize_phone((row.get(phone_col) or "").strip())
        if not phone:
            invalid += 1
            continue
        if phone in seen:
            skipped += 1
            continue
        name = (row.get(name_col) or "").strip() if name_col else ""
        opted_in = bool(optin_col) and (row.get(optin_col) or "").strip().lower() in _TRUTHY
        db.add(Lead(
            whatsapp_opt_in=opted_in,
            whatsapp_opt_in_at=now if opted_in else None,
            whatsapp_opt_in_source="csv_import" if opted_in else None,
            account_id=current_user.tenant_id,
            name=name or phone,
            instagram_handle=phone,
            phone=phone,
            source=LeadSource.MANUAL,
            status=LeadStatus.NEW,
        ))
        seen.add(phone)
        created += 1

    await db.flush()
    logger.info("Import CSV: tenant=%s created=%d skipped=%d invalid=%d",
                current_user.tenant_id, created, skipped, invalid)
    return {"created": created, "skipped": skipped, "invalid": invalid}


@router.get("", response_model=List[LeadResponse])
async def list_leads(
    status: Optional[str] = Query(None),
    score_label: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    query = (
        select(Lead)
        .where(Lead.account_id == current_user.tenant_id)
        .order_by(Lead.captured_at.desc())
    )
    result = await db.execute(query)
    leads = result.scalars().all()

    if status:
        leads = [l for l in leads if l.status == status]
    if score_label:
        leads = [l for l in leads if l.score_label == score_label]
    if search:
        s = search.lower()
        leads = [
            l for l in leads
            if s in (l.name or "").lower()
            or s in (l.instagram_handle or "").lower()
            or s in (l.email or "").lower()
        ]

    return leads


@router.get("/{lead_id}", response_model=LeadResponse)
async def get_lead(
    lead_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(Lead).where(
            Lead.id == lead_id,
            Lead.account_id == current_user.tenant_id,
        )
    )
    lead = result.scalar_one_or_none()
    if not lead:
        raise HTTPException(status_code=404, detail="Lead não encontrado")
    return lead


@router.put("/{lead_id}", response_model=LeadResponse)
async def update_lead(
    lead_id: str,
    data: LeadUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(Lead).where(
            Lead.id == lead_id,
            Lead.account_id == current_user.tenant_id,
        )
    )
    lead = result.scalar_one_or_none()
    if not lead:
        raise HTTPException(status_code=404, detail="Lead não encontrado")

    updates = data.model_dump(exclude_unset=True)
    phone_changed = "phone" in updates and updates["phone"] and updates["phone"] != lead.phone
    email_changed = "email" in updates and updates["email"] and updates["email"] != lead.email
    for field, value in updates.items():
        setattr(lead, field, value)

    # Preencher telefone/email pode revelar que este lead é a mesma pessoa de
    # outro (ex: lead do Instagram que agora ganhou o número do WhatsApp) — unifica.
    if phone_changed or email_changed:
        await db.flush()
        if phone_changed:
            lead = await auto_merge_by_phone(lead, db)
        if email_changed:
            lead = await auto_merge_by_email(lead, db)

    await score_lead(lead)
    await db.flush()
    await db.refresh(lead)
    return lead


@router.put("/{lead_id}/consent", response_model=LeadResponse)
async def update_lead_consent(
    lead_id: str,
    data: LeadConsentUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Records WhatsApp opt-in (with timestamp and source) or opt-out for a lead.
    Business-initiated (template) messages are only sent to opted-in leads.
    """
    result = await db.execute(
        select(Lead).where(Lead.id == lead_id, Lead.account_id == current_user.tenant_id)
    )
    lead = result.scalar_one_or_none()
    if not lead:
        raise HTTPException(status_code=404, detail="Lead não encontrado")

    now = datetime.now(timezone.utc)
    if data.whatsapp_opt_in:
        lead.whatsapp_opt_in = True
        lead.whatsapp_opt_in_at = now
        lead.whatsapp_opt_in_source = data.source[:50]
        lead.whatsapp_opted_out_at = None
    else:
        lead.whatsapp_opt_in = False
        lead.whatsapp_opted_out_at = now
    await db.flush()
    await db.refresh(lead)
    return lead


@router.post("/{lead_id}/merge", response_model=LeadResponse)
async def merge_lead(
    lead_id: str,
    body: MergeLeadsRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Mescla manualmente dois leads da mesma pessoa em um só. `lead_id` é o
    sobrevivente; `absorbed_lead_id` é fundido nele e removido. Todo o
    histórico de conversas do absorvido passa para o sobrevivente.
    """
    if lead_id == body.absorbed_lead_id:
        raise HTTPException(400, "Não é possível mesclar um lead com ele mesmo.")

    result = await db.execute(
        select(Lead).where(
            Lead.id.in_([lead_id, body.absorbed_lead_id]),
            Lead.account_id == current_user.tenant_id,
        )
    )
    leads = {l.id: l for l in result.scalars().all()}
    survivor = leads.get(lead_id)
    absorbed = leads.get(body.absorbed_lead_id)
    if not survivor or not absorbed:
        raise HTTPException(404, "Um ou ambos os leads não foram encontrados.")

    survivor = await merge_leads(survivor, absorbed, db)
    await score_lead(survivor)
    await db.flush()
    await db.refresh(survivor)
    return survivor


@router.post("/{lead_id}/score", response_model=LeadResponse)
async def score_lead_endpoint(
    lead_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Recalcula o score de um lead específico."""
    result = await db.execute(
        select(Lead).where(
            Lead.id == lead_id,
            Lead.account_id == current_user.tenant_id,
        )
    )
    lead = result.scalar_one_or_none()
    if not lead:
        raise HTTPException(status_code=404, detail="Lead não encontrado")

    await score_lead(lead)
    await db.flush()
    await db.refresh(lead)
    return lead


@router.post("/score-all", response_model=dict)
async def score_all_leads(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Recalcula o score de todos os leads da conta."""
    result = await db.execute(
        select(Lead).where(Lead.account_id == current_user.tenant_id)
    )
    leads = result.scalars().all()

    for lead in leads:
        await score_lead(lead)

    await db.flush()
    return {"scored": len(leads)}


@router.delete("/{lead_id}")
async def delete_lead(
    lead_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(Lead).where(
            Lead.id == lead_id,
            Lead.account_id == current_user.tenant_id,
        )
    )
    lead = result.scalar_one_or_none()
    if not lead:
        raise HTTPException(status_code=404, detail="Lead não encontrado")

    await db.delete(lead)
    await db.flush()
    return {"detail": "Lead removido"}
