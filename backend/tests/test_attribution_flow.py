"""
Testes da atribuição de anúncios e do resolvedor único de identidade:
  - resolve_or_create_lead: cascata external_id → telefone → email, anexando
    o external_id novo em alt_handles (sem duplicar)
  - auto_merge_by_email
  - CTWA: mensagem do WhatsApp com referral grava origin_ad_id no lead
  - IG Direct: messaging com referral grava origin_ad_id
  - Lead Ads (leadgen): busca os dados na Graph (mock) e funde com lead
    existente por telefone em vez de duplicar
"""
import hashlib
import hmac
import json
import uuid

import pytest
from sqlalchemy import select
from unittest.mock import AsyncMock, patch

from app.models.account import Account
from app.models.lead import Lead, LeadSource
from app.models.meta_connection import (
    MetaConnection, PROVIDER_WHATSAPP, PROVIDER_INSTAGRAM, PROVIDER_ADS, STATUS_ACTIVE,
)
from app.services.meta_token_service import encrypt_token
from app.services.lead_identity import resolve_or_create_lead
from app.services.lead_merge import auto_merge_by_email

APP_SECRET = "test_app_secret"


def _sig(body: bytes) -> str:
    return "sha256=" + hmac.new(APP_SECRET.encode(), body, hashlib.sha256).hexdigest()


async def _post(client, payload: dict):
    body = json.dumps(payload).encode()
    return await client.post(
        "/api/v1/webhook/meta", content=body,
        headers={"Content-Type": "application/json", "X-Hub-Signature-256": _sig(body)},
    )


@pytest.fixture(autouse=True)
def _mock_ig_calls():
    with patch("app.services.instagram_service.get_user_profile", new_callable=AsyncMock,
               return_value={"name": "Cliente Ads", "username": "cliente_ads", "profile_pic": None}), \
         patch("app.services.whatsapp_service.mark_as_read", new_callable=AsyncMock):
        yield


# ---------------------------------------------------------------------------
# Resolvedor de identidade
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_resolver_cascata_telefone_anexa_external_id(db_session):
    account = Account(brand_name="Resolver Test")
    db_session.add(account)
    await db_session.flush()

    # Lead existente do WhatsApp (external = número)
    wa = await resolve_or_create_lead(
        db_session, account.id,
        external_id="5583988887777", phone="5583988887777", name="Maria",
        source=LeadSource.MANUAL,
    )

    # Chega a MESMA pessoa por outro canal (Lead Ads) — só telefone em comum
    same = await resolve_or_create_lead(
        db_session, account.id,
        external_id="PSID_NOVO", phone="5583988887777", email="maria@x.com",
        source=LeadSource.INSTAGRAM_FORM, origin_ad_id="AD_1",
    )

    assert same.id == wa.id                      # não duplicou
    assert same.email == "maria@x.com"           # completou o email
    assert same.origin_ad_id == "AD_1"           # ganhou a atribuição
    assert ",PSID_NOVO," in same.alt_handles     # canal novo registrado

    # Próxima mensagem daquele canal acha direto pelo external_id (passo 1)
    again = await resolve_or_create_lead(db_session, account.id, external_id="PSID_NOVO")
    assert again.id == wa.id

    total = (await db_session.execute(
        select(Lead).where(Lead.account_id == account.id)
    )).scalars().all()
    assert len(total) == 1


@pytest.mark.asyncio
async def test_resolver_encontra_por_email(db_session):
    account = Account(brand_name="Email Test")
    db_session.add(account)
    await db_session.flush()

    first = await resolve_or_create_lead(
        db_session, account.id, external_id="X1", email="Joao@Email.com",
    )
    # Email com caixa diferente ainda casa (normalizado)
    found = await resolve_or_create_lead(
        db_session, account.id, external_id="X2", email="joao@email.com",
    )
    assert found.id == first.id


@pytest.mark.asyncio
async def test_auto_merge_by_email(db_session):
    account = Account(brand_name="Merge Email")
    db_session.add(account)
    await db_session.flush()

    a = Lead(id=str(uuid.uuid4()), account_id=account.id, instagram_handle="A",
             name="Ana", email="ana@x.com", source=LeadSource.INSTAGRAM_DM)
    b = Lead(id=str(uuid.uuid4()), account_id=account.id, instagram_handle="B",
             name="B", email="ana@x.com", source=LeadSource.MANUAL)
    db_session.add_all([a, b])
    await db_session.flush()

    survivor = await auto_merge_by_email(b, db_session)
    remaining = (await db_session.execute(
        select(Lead).where(Lead.account_id == account.id)
    )).scalars().all()
    assert len(remaining) == 1
    assert remaining[0].id == survivor.id


# ---------------------------------------------------------------------------
# CTWA — Click-to-WhatsApp: referral no webhook grava a origem
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_ctwa_referral_atribui_anuncio(client, db_session):
    account = Account(brand_name="CTWA Test")
    db_session.add(account)
    await db_session.flush()
    db_session.add(MetaConnection(
        id=str(uuid.uuid4()), account_id=account.id, provider=PROVIDER_WHATSAPP,
        phone_number_id="PNI_CTWA", waba_id="WABA_C",
        access_token_encrypted=encrypt_token("fake"), status=STATUS_ACTIVE,
    ))
    await db_session.flush()

    payload = {
        "object": "whatsapp_business_account",
        "entry": [{"id": "E", "changes": [{"field": "messages", "value": {
            "messaging_product": "whatsapp",
            "metadata": {"display_phone_number": "5583", "phone_number_id": "PNI_CTWA"},
            "contacts": [{"wa_id": "5583911112222", "profile": {"name": "Pedro"}}],
            "messages": [{
                "from": "5583911112222", "id": "wamid.CTWA1", "timestamp": "1",
                "type": "text", "text": {"body": "Vi o anúncio!"},
                "referral": {
                    "source_url": "https://fb.me/xyz", "source_type": "ad",
                    "source_id": "AD_CTWA_99", "headline": "Promo",
                    "ctwa_clid": "clid123",
                },
            }],
        }}]}],
    }
    resp = await _post(client, payload)
    assert resp.status_code == 200

    lead = (await db_session.execute(
        select(Lead).where(Lead.account_id == account.id)
    )).scalar_one()
    assert lead.origin_ad_id == "AD_CTWA_99"
    meta = json.loads(lead.metadata_json)
    assert meta["ad_referral"]["ctwa_clid"] == "clid123"


# ---------------------------------------------------------------------------
# IG Direct — referral de anúncio na DM
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_ig_dm_referral_atribui_anuncio(client, db_session):
    account = Account(brand_name="IG Ref Test")
    db_session.add(account)
    await db_session.flush()
    db_session.add(MetaConnection(
        id=str(uuid.uuid4()), account_id=account.id, provider=PROVIDER_INSTAGRAM,
        ig_business_account_id="IGREF", meta_user_id="IGREF",
        access_token_encrypted=encrypt_token("fake"), status=STATUS_ACTIVE,
    ))
    await db_session.flush()

    payload = {"object": "instagram", "entry": [{"id": "IGREF", "messaging": [{
        "sender": {"id": "PSID_REF"}, "recipient": {"id": "IGREF"}, "timestamp": 1,
        "message": {"mid": "MID_REF", "text": "vim pelo anúncio"},
        "referral": {"ad_id": "AD_IG_55", "source": "ADS", "type": "OPEN_THREAD"},
    }]}]}
    resp = await _post(client, payload)
    assert resp.status_code == 200

    lead = (await db_session.execute(
        select(Lead).where(Lead.account_id == account.id)
    )).scalar_one()
    assert lead.origin_ad_id == "AD_IG_55"


# ---------------------------------------------------------------------------
# Lead Ads — leadgen busca dados e NÃO duplica lead existente
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_leadgen_funde_com_lead_existente_por_telefone(client, db_session):
    account = Account(brand_name="Leadgen Test", meta_page_id="PAGE_LG")
    db_session.add(account)
    await db_session.flush()
    db_session.add(MetaConnection(
        id=str(uuid.uuid4()), account_id=account.id, provider=PROVIDER_ADS,
        ad_account_id="act_1", page_id="PAGE_LG",
        access_token_encrypted=encrypt_token("ads_token"), status=STATUS_ACTIVE,
    ))
    # Lead que já falou pelo WhatsApp antes
    existing = Lead(
        id=str(uuid.uuid4()), account_id=account.id,
        instagram_handle="5583900001111", phone="5583900001111",
        name="5583900001111", source=LeadSource.INSTAGRAM_DM,
    )
    db_session.add(existing)
    await db_session.flush()

    payload = {"object": "page", "entry": [{"id": "PAGE_LG", "changes": [{
        "field": "leadgen",
        "value": {"leadgen_id": "LG1", "page_id": "PAGE_LG",
                  "form_id": "F1", "ad_id": "AD_FORM_7"},
    }]}]}

    with patch("app.services.ads_service.get_leadgen", new_callable=AsyncMock,
               return_value={
                   "id": "LG1", "ad_id": "AD_FORM_7",
                   "field_data": [
                       {"name": "full_name", "values": ["Carlos Souza"]},
                       {"name": "email", "values": ["carlos@x.com"]},
                       {"name": "phone_number", "values": ["+55 83 90000-1111"]},
                   ],
               }):
        resp = await _post(client, payload)
    assert resp.status_code == 200

    leads = (await db_session.execute(
        select(Lead).where(Lead.account_id == account.id)
    )).scalars().all()
    assert len(leads) == 1                         # fundiu, não duplicou
    lead = leads[0]
    assert lead.email == "carlos@x.com"            # formulário completou o email
    assert lead.name == "Carlos Souza"             # e o nome real
    assert lead.origin_ad_id == "AD_FORM_7"        # atribuição do anúncio
