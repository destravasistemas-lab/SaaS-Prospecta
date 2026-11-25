"""
Prospecção.

Lista por CNPJ (dados abertos da Receita Federal): a conta busca por atividade
(CNAE) e cidade, vê quantas empresas existem e paga a lista por Pix. Depois do
pagamento baixa o CSV ou puxa para os Leads. CNPJ entregue para a conta não
volta nas próximas buscas dela; CNPJ reservado num pedido em aberto também não.

Google Maps: só consulta dentro do app (os termos do Google não permitem salvar
nem exportar os resultados), com limite diário por conta.
"""
import csv
import io
import json
import logging
import re
import unicodedata
from datetime import datetime, timedelta, timezone

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy import exists, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_db
from app.core.i18n import t
from app.core.modules import is_super_admin
from app.core.phone import normalize_phone
from app.core.security import get_current_user
from app.models.lead import Lead, LeadSource, LeadStatus
from app.models.prospect import (
    ORDER_PAID, ORDER_PENDING, CnpjCnae, CnpjCompany, CnpjImportInfo, CnpjMunicipio,
    PlacesSearchLog, ProspectDelivered, ProspectOrder,
)
from app.models.user import User
from app.services.asaas_service import asaas_service

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/prospect", tags=["prospect"])

RESERVATION_HOURS = 24
PREVIEW_ROWS = 5
PORTES = {"00": "Não informado", "01": "Microempresa", "03": "Pequeno porte", "05": "Demais"}
PLACES_URL = "https://places.googleapis.com/v1/places:searchText"
PLACES_FIELDS = ",".join([
    "places.id", "places.displayName", "places.formattedAddress", "places.nationalPhoneNumber",
    "places.internationalPhoneNumber", "places.websiteUri", "places.googleMapsUri",
    "places.rating", "places.userRatingCount", "places.businessStatus", "nextPageToken",
])


def normalize_search(text: str) -> str:
    text = unicodedata.normalize("NFKD", text or "").encode("ascii", "ignore").decode()
    return re.sub(r"\s+", " ", text.lower()).strip()


def price_for(quantity: int) -> float:
    if quantity <= 0:
        return 0.0
    return round(max(settings.prospect_min_order, quantity * settings.prospect_price_per_contact), 2)


def format_phone(phone: str | None) -> str:
    if not phone:
        return ""
    d = phone[2:] if phone.startswith("55") and len(phone) > 11 else phone
    if len(d) == 11:
        return f"({d[:2]}) {d[2:7]}-{d[7:]}"
    if len(d) == 10:
        return f"({d[:2]}) {d[2:6]}-{d[6:]}"
    return phone


def _mask_phone(phone: str | None) -> str:
    f = format_phone(phone)
    return f[:5] + re.sub(r"\d", "•", f[5:-2]) + f[-2:] if len(f) > 7 else ""


def _mask_email(email: str | None) -> str:
    if not email or "@" not in email:
        return ""
    user, domain = email.split("@", 1)
    return f"{user[:2]}•••@{domain}"


class SearchIn(BaseModel):
    cnae: str = Field(..., min_length=7, max_length=7, pattern=r"^\d{7}$")
    municipio_code: str = Field(..., min_length=1, max_length=4, pattern=r"^\d{1,4}$")
    bairro: str | None = Field(default=None, max_length=120)
    only_phone: bool = True
    only_email: bool = False
    exclude_mei: bool = False
    include_secondary: bool = False
    quantity: int | None = Field(default=None, ge=1)


class OrderIn(SearchIn):
    buyer_name: str = Field(..., min_length=2, max_length=120)
    buyer_document: str = Field(..., min_length=11, max_length=18)


async def _reserved(db: AsyncSession, account_id: str) -> set[str]:
    since = datetime.now(timezone.utc) - timedelta(hours=RESERVATION_HOURS)
    rows = (await db.execute(
        select(ProspectOrder.cnpjs).where(
            ProspectOrder.account_id == account_id,
            ProspectOrder.status == ORDER_PENDING,
            ProspectOrder.created_at >= since,
        )
    )).scalars().all()
    return {c for lst in rows for c in (lst or [])}


def _filtered(account_id: str, body: SearchIn, reserved: set[str]):
    q = select(CnpjCompany).where(CnpjCompany.municipio_code == body.municipio_code.zfill(4))
    if body.include_secondary:
        q = q.where((CnpjCompany.cnae == body.cnae) | CnpjCompany.cnaes_secundarios.contains(f",{body.cnae},"))
    else:
        q = q.where(CnpjCompany.cnae == body.cnae)
    if body.only_phone:
        q = q.where(CnpjCompany.telefone1.isnot(None))
    if body.only_email:
        q = q.where(CnpjCompany.email.isnot(None))
    if body.exclude_mei:
        q = q.where(CnpjCompany.mei.is_(False))
    if body.bairro and body.bairro.strip():
        q = q.where(func.upper(CnpjCompany.bairro).contains(body.bairro.strip().upper()))
    q = q.where(~exists().where(
        ProspectDelivered.account_id == account_id, ProspectDelivered.cnpj == CnpjCompany.cnpj,
    ))
    if reserved:
        q = q.where(CnpjCompany.cnpj.notin_(reserved))
    return q


def _max_quantity(body: SearchIn, available: int) -> int:
    wanted = body.quantity or available
    return max(0, min(wanted, available, settings.prospect_max_per_order))


@router.get("/status")
async def prospect_status(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    info = await db.get(CnpjImportInfo, 1)
    return {
        "cnpj_available": bool(info and info.total),
        "reference_month": info.reference_month if info else None,
        "ufs": info.ufs.split(",") if info else [],
        "total": info.total if info else 0,
        "price_per_contact": settings.prospect_price_per_contact,
        "min_order": settings.prospect_min_order,
        "max_per_order": settings.prospect_max_per_order,
        "maps_enabled": bool(settings.google_maps_api_key),
        "maps_searches_per_day": settings.google_maps_searches_per_day,
        "free": is_super_admin(current_user),
    }


@router.get("/cnaes")
async def search_cnaes(
    q: str = Query(..., min_length=2, max_length=80),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    term = normalize_search(q)
    digits = re.sub(r"\D", "", q)
    stmt = select(CnpjCnae)
    if len(digits) >= 4:
        stmt = stmt.where(CnpjCnae.code.startswith(digits))
    else:
        for word in term.split(" ")[:4]:
            stmt = stmt.where(CnpjCnae.search.contains(word))
    rows = (await db.execute(stmt.order_by(CnpjCnae.description).limit(20))).scalars().all()
    return [{"code": r.code, "description": r.description} for r in rows]


@router.get("/cities")
async def search_cities(
    q: str = Query(..., min_length=2, max_length=80),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    stmt = select(CnpjMunicipio).where(
        CnpjMunicipio.search.startswith(normalize_search(q)), CnpjMunicipio.uf.isnot(None),
    ).order_by(CnpjMunicipio.name).limit(20)
    rows = (await db.execute(stmt)).scalars().all()
    return [{"code": r.code, "name": r.name, "uf": r.uf} for r in rows]


@router.post("/quote")
async def quote(
    body: SearchIn,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Quantas empresas novas existem para a busca, quanto custa e uma prévia mascarada."""
    base = _filtered(current_user.tenant_id, body, await _reserved(db, current_user.tenant_id))
    available = (await db.execute(select(func.count()).select_from(base.subquery()))).scalar() or 0
    already = (await db.execute(
        select(func.count(ProspectDelivered.id)).where(ProspectDelivered.account_id == current_user.tenant_id)
    )).scalar() or 0
    quantity = _max_quantity(body, available)
    preview = (await db.execute(base.order_by(CnpjCompany.cnpj).limit(PREVIEW_ROWS))).scalars().all()
    return {
        "available": available,
        "quantity": quantity,
        "amount": 0.0 if is_super_admin(current_user) else price_for(quantity),
        "already_delivered_total": already,
        "preview": [
            {
                "name": c.nome_fantasia or c.razao_social,
                "bairro": c.bairro,
                "phone": _mask_phone(c.telefone1),
                "email": _mask_email(c.email),
                "porte": PORTES.get(c.porte or "", ""),
            }
            for c in preview
        ],
    }


def _serialize_order(o: ProspectOrder, *, with_pix: bool = False) -> dict:
    data = {
        "id": o.id,
        "status": o.status,
        "cnae": o.cnae,
        "municipio_code": o.municipio_code,
        "filters": o.filters or {},
        "quantity": o.quantity,
        "amount": o.amount,
        "created_at": o.created_at.isoformat() if o.created_at else None,
        "paid_at": o.paid_at.isoformat() if o.paid_at else None,
        "invoice_url": o.invoice_url,
    }
    if with_pix and o.status == ORDER_PENDING:
        data["pix_payload"] = o.pix_payload
        data["pix_image"] = o.pix_image
    return data


async def mark_order_paid(db: AsyncSession, order: ProspectOrder) -> None:
    """Pagamento confirmado: entrega os CNPJs reservados (idempotente)."""
    if order.status == ORDER_PAID:
        return
    order.status = ORDER_PAID
    order.paid_at = datetime.now(timezone.utc)
    have = set((await db.execute(
        select(ProspectDelivered.cnpj).where(
            ProspectDelivered.account_id == order.account_id,
            ProspectDelivered.cnpj.in_(order.cnpjs or []),
        )
    )).scalars().all())
    for cnpj in order.cnpjs or []:
        if cnpj not in have:
            db.add(ProspectDelivered(account_id=order.account_id, cnpj=cnpj, order_id=order.id))
            have.add(cnpj)
    await db.flush()


@router.post("/orders", status_code=201)
async def create_order(
    body: OrderIn,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    document = re.sub(r"\D", "", body.buyer_document)
    if len(document) not in (11, 14):
        raise HTTPException(422, t("Informe um CPF ou CNPJ válido para o Pix.", "Enter a valid CPF or CNPJ for the Pix charge."))
    free = is_super_admin(current_user)
    if not free and not settings.asaas_api_key:
        raise HTTPException(503, t("O pagamento por Pix ainda não está configurado.", "Pix payment is not configured yet."))

    base = _filtered(current_user.tenant_id, body, await _reserved(db, current_user.tenant_id))
    available = (await db.execute(select(func.count()).select_from(base.subquery()))).scalar() or 0
    quantity = _max_quantity(body, available)
    if quantity == 0:
        raise HTTPException(409, t(
            "Não há empresas novas para essa busca. As que você já comprou não voltam.",
            "There are no new companies for this search. The ones you already bought don't come back.",
        ))
    picked = base.order_by(CnpjCompany.cnpj).limit(quantity).subquery()
    cnpjs = list((await db.execute(select(picked.c.cnpj))).scalars().all())

    order = ProspectOrder(
        account_id=current_user.tenant_id,
        user_id=current_user.id,
        cnae=body.cnae,
        municipio_code=body.municipio_code.zfill(4),
        filters=body.model_dump(exclude={"buyer_name", "buyer_document", "cnae", "municipio_code"}),
        cnpjs=cnpjs,
        quantity=len(cnpjs),
        amount=0.0 if free else price_for(len(cnpjs)),
    )
    db.add(order)
    await db.flush()

    if free:
        await mark_order_paid(db, order)
        return _serialize_order(order)

    previous = (await db.execute(
        select(ProspectOrder.asaas_customer_id).where(
            ProspectOrder.account_id == current_user.tenant_id,
            ProspectOrder.asaas_customer_id.isnot(None),
        ).order_by(ProspectOrder.created_at.desc()).limit(1)
    )).scalar_one_or_none()
    try:
        customer_id = previous or (await asaas_service.create_customer(
            name=body.buyer_name.strip(),
            email=current_user.username if "@" in (current_user.username or "") else "sem-email@prospecta.app",
            cpf_cnpj=document,
        )).get("id")
        payment = await asaas_service.create_payment(
            customer_id=customer_id,
            value=order.amount,
            due_date=asaas_service.calculate_due_date(days_ahead=1),
            description=f"Lista de prospecção: {order.quantity} empresas",
            billing_type="PIX",
        )
    except Exception:
        raise HTTPException(502, t(
            "Não foi possível gerar o Pix agora. Tente de novo em instantes.",
            "Could not create the Pix charge right now. Try again shortly.",
        ))
    order.asaas_customer_id = customer_id
    order.asaas_payment_id = payment.get("id")
    order.invoice_url = payment.get("invoiceUrl")
    try:
        qr = await asaas_service.get_pix_qr(order.asaas_payment_id)
        order.pix_payload = qr.get("payload")
        order.pix_image = qr.get("encodedImage")
    except Exception as exc:
        logger.warning("QR do Pix indisponível para o pedido %s: %s", order.id, exc)
    await db.flush()
    return _serialize_order(order, with_pix=True)


async def _order_or_404(db: AsyncSession, order_id: str, account_id: str) -> ProspectOrder:
    order = await db.get(ProspectOrder, order_id)
    if not order or order.account_id != account_id:
        raise HTTPException(404, t("Pedido não encontrado.", "Order not found."))
    return order


@router.get("/orders")
async def list_orders(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    rows = (await db.execute(
        select(ProspectOrder).where(ProspectOrder.account_id == current_user.tenant_id)
        .order_by(ProspectOrder.created_at.desc()).limit(50)
    )).scalars().all()
    names = await _labels(db, {o.cnae for o in rows}, {o.municipio_code for o in rows})
    return [{**_serialize_order(o), **_label_of(o, names)} for o in rows]


@router.get("/orders/{order_id}")
async def get_order(
    order_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Status do pedido. Enquanto pendente, confere o pagamento direto no Asaas (não depende só do webhook)."""
    order = await _order_or_404(db, order_id, current_user.tenant_id)
    if order.status == ORDER_PENDING and order.asaas_payment_id:
        try:
            payment = await asaas_service.get_payment(order.asaas_payment_id)
            if payment.get("status") in ("RECEIVED", "CONFIRMED", "RECEIVED_IN_CASH"):
                await mark_order_paid(db, order)
        except Exception:
            pass
    return _serialize_order(order, with_pix=True)


async def _labels(db: AsyncSession, cnaes: set[str], cities: set[str]) -> dict:
    cn = dict((await db.execute(select(CnpjCnae.code, CnpjCnae.description).where(CnpjCnae.code.in_(cnaes or {""})))).all())
    ct = {c: (n, uf) for c, n, uf in (await db.execute(
        select(CnpjMunicipio.code, CnpjMunicipio.name, CnpjMunicipio.uf).where(CnpjMunicipio.code.in_(cities or {""}))
    )).all()}
    return {"cnae": cn, "city": ct}


def _label_of(o: ProspectOrder, names: dict) -> dict:
    city = names["city"].get(o.municipio_code)
    return {
        "cnae_description": names["cnae"].get(o.cnae, o.cnae),
        "city": f"{city[0]} - {city[1]}" if city else o.municipio_code,
    }


async def _companies(db: AsyncSession, cnpjs: list[str]) -> list[CnpjCompany]:
    out: list[CnpjCompany] = []
    for i in range(0, len(cnpjs), 500):
        out += (await db.execute(select(CnpjCompany).where(CnpjCompany.cnpj.in_(cnpjs[i:i + 500])))).scalars().all()
    return sorted(out, key=lambda c: c.cnpj)


def _require_paid(order: ProspectOrder) -> None:
    if order.status != ORDER_PAID:
        raise HTTPException(402, t("A lista é liberada depois que o Pix for pago.", "The list is released once the Pix is paid."))


@router.get("/orders/{order_id}/csv")
async def download_csv(
    order_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    order = await _order_or_404(db, order_id, current_user.tenant_id)
    _require_paid(order)
    companies = await _companies(db, order.cnpjs or [])
    names = await _labels(db, {c.cnae for c in companies}, {c.municipio_code for c in companies})

    buf = io.StringIO()
    buf.write("﻿")
    w = csv.writer(buf, delimiter=";")
    w.writerow(["cnpj", "razao_social", "nome_fantasia", "telefone", "telefone_2", "email",
                "atividade", "endereco", "bairro", "cidade", "uf", "cep", "porte", "abertura"])
    for c in companies:
        city = names["city"].get(c.municipio_code, ("", c.uf))
        cnpj = f"{c.cnpj[:2]}.{c.cnpj[2:5]}.{c.cnpj[5:8]}/{c.cnpj[8:12]}-{c.cnpj[12:]}"
        abertura = f"{c.abertura[6:]}/{c.abertura[4:6]}/{c.abertura[:4]}" if c.abertura and len(c.abertura) == 8 else ""
        w.writerow([cnpj, c.razao_social or "", c.nome_fantasia or "", format_phone(c.telefone1), format_phone(c.telefone2),
                    c.email or "", names["cnae"].get(c.cnae, c.cnae), c.endereco or "", c.bairro or "",
                    city[0], c.uf, c.cep or "", PORTES.get(c.porte or "", ""), abertura])
    filename = f"prospeccao-{order.created_at:%Y%m%d}-{order.id[:8]}.csv"
    return StreamingResponse(
        iter([buf.getvalue().encode("utf-8")]),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.post("/orders/{order_id}/import-leads")
async def import_leads(
    order_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Puxa as empresas da lista para os Leads (sem opt-in; telefones já existentes são pulados)."""
    order = await _order_or_404(db, order_id, current_user.tenant_id)
    _require_paid(order)
    companies = await _companies(db, order.cnpjs or [])
    seen = set((await db.execute(
        select(Lead.phone).where(Lead.account_id == current_user.tenant_id, Lead.phone.isnot(None))
    )).scalars().all())
    created = skipped = 0
    for c in companies:
        phone = normalize_phone(c.telefone1)
        if not phone or phone in seen:
            skipped += 1
            continue
        seen.add(phone)
        db.add(Lead(
            account_id=current_user.tenant_id,
            name=(c.nome_fantasia or c.razao_social or phone)[:255],
            instagram_handle=phone,
            phone=phone,
            email=c.email,
            source=LeadSource.MANUAL,
            status=LeadStatus.NEW,
            metadata_json=json.dumps({"cnpj": c.cnpj, "razao_social": c.razao_social,
                                      "origem": "prospeccao_cnpj", "pedido": order.id}, ensure_ascii=False),
        ))
        created += 1
    await db.flush()
    return {"created": created, "skipped": skipped}


# ---------------------------------------------------------------------------
# Google Maps (consulta no app; nada é salvo)
# ---------------------------------------------------------------------------

@router.get("/places")
async def search_places(
    q: str = Query(..., min_length=3, max_length=150),
    page_token: str | None = Query(default=None, max_length=1000),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if not settings.google_maps_api_key:
        raise HTTPException(503, t("A busca no Google Maps ainda não está configurada.", "Google Maps search is not configured yet."))
    local_midnight = (datetime.now(timezone.utc) - timedelta(hours=3)).replace(hour=0, minute=0, second=0, microsecond=0)
    since = local_midnight + timedelta(hours=3)
    used = (await db.execute(
        select(func.count(PlacesSearchLog.id)).where(
            PlacesSearchLog.account_id == current_user.tenant_id, PlacesSearchLog.created_at >= since,
        )
    )).scalar() or 0
    limit = settings.google_maps_searches_per_day
    if used >= limit and not is_super_admin(current_user):
        raise HTTPException(429, t(
            f"Você usou as {limit} buscas de hoje no Google Maps. Amanhã libera de novo.",
            f"You used today's {limit} Google Maps searches. They reset tomorrow.",
        ))

    payload = {"textQuery": q, "languageCode": "pt-BR", "regionCode": "BR", "pageSize": 20}
    if page_token:
        payload["pageToken"] = page_token
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            r = await client.post(PLACES_URL, json=payload, headers={
                "X-Goog-Api-Key": settings.google_maps_api_key, "X-Goog-FieldMask": PLACES_FIELDS,
            })
    except httpx.HTTPError:
        raise HTTPException(502, t("O Google Maps não respondeu. Tente de novo.", "Google Maps did not respond. Try again."))
    if r.status_code != 200:
        logger.warning("Places API %s: %s", r.status_code, r.text[:300])
        raise HTTPException(502, t("O Google Maps recusou a busca.", "Google Maps rejected the search."))

    db.add(PlacesSearchLog(account_id=current_user.tenant_id))
    await db.flush()
    data = r.json()
    return {
        "used_today": used + 1,
        "limit": limit,
        "next_page_token": data.get("nextPageToken"),
        "places": [
            {
                "id": p.get("id"),
                "name": (p.get("displayName") or {}).get("text"),
                "address": p.get("formattedAddress"),
                "phone": p.get("nationalPhoneNumber"),
                "phone_intl": p.get("internationalPhoneNumber"),
                "website": p.get("websiteUri"),
                "maps_url": p.get("googleMapsUri"),
                "rating": p.get("rating"),
                "reviews": p.get("userRatingCount"),
                "status": p.get("businessStatus"),
            }
            for p in data.get("places", [])
        ],
    }
