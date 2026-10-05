"""
Tests for cross-channel lead unification:
  - manual merge endpoint (reassigns conversations, fills fields, deletes dup)
  - auto-merge by phone
  - _find_lead matching absorbed identifiers via alt_handles (so future
    messages find the unified lead instead of recreating the duplicate)
"""
import uuid
from datetime import datetime, timezone, timedelta

import pytest
from sqlalchemy import select

from app.core.security import create_access_token
from app.models.account import Account
from app.models.user import User
from app.models.lead import Lead, LeadSource, LeadStatus
from app.models.conversation import Conversation
from app.routes.webhook import _find_lead
from app.services.lead_merge import merge_leads, auto_merge_by_phone


async def _account_and_user(db_session):
    account = Account(brand_name="Merge Test")
    db_session.add(account)
    await db_session.flush()
    user = User(
        id=str(uuid.uuid4()), tenant_id=account.id, username=f"u_{uuid.uuid4().hex[:8]}",
        password_hash="x", role="admin", is_active=True,
    )
    db_session.add(user)
    await db_session.flush()
    headers = {"Authorization": f"Bearer {create_access_token(user.id, account.id, 'admin')}"}
    return account, headers


def _lead(account_id, handle, **kw):
    return Lead(
        id=str(uuid.uuid4()),
        account_id=account_id,
        instagram_handle=handle,
        name=kw.pop("name", handle),
        source=kw.pop("source", LeadSource.INSTAGRAM_DM),
        status=LeadStatus.NEW,
        **kw,
    )


# ---------------------------------------------------------------------------
# merge_leads core behaviour
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_merge_moves_conversations_and_fills_fields(db_session):
    account, _ = await _account_and_user(db_session)

    ig_lead = _lead(account.id, "PSID_IG", name="Maria Silva")   # tem nome real
    wa_lead = _lead(account.id, "5583999", name="5583999", phone="+5583999")  # tem telefone
    db_session.add_all([ig_lead, wa_lead])
    await db_session.flush()

    # conversa do WhatsApp aponta para o lead do WhatsApp
    conv = Conversation(id=str(uuid.uuid4()), tenant_id=account.id, customer_id=wa_lead.id, channel="whatsapp")
    db_session.add(conv)
    await db_session.flush()

    survivor = await merge_leads(ig_lead, wa_lead, db_session)

    # a conversa migrou para o sobrevivente
    await db_session.refresh(conv)
    assert conv.customer_id == survivor.id
    # o telefone do lead absorvido foi preenchido no sobrevivente
    assert survivor.phone == "+5583999"
    # nome real preservado
    assert survivor.name == "Maria Silva"
    # o handle do absorvido virou alt_handle
    assert ",5583999," in survivor.alt_handles
    # o lead absorvido foi removido
    gone = await db_session.get(Lead, wa_lead.id)
    assert gone is None


@pytest.mark.asyncio
async def test_find_lead_matches_absorbed_handle(db_session):
    account, _ = await _account_and_user(db_session)
    ig_lead = _lead(account.id, "PSID_IG", name="João")
    wa_lead = _lead(account.id, "5584888", phone="+5584888")
    db_session.add_all([ig_lead, wa_lead])
    await db_session.flush()

    survivor = await merge_leads(ig_lead, wa_lead, db_session)

    # Uma mensagem futura do WhatsApp (procura pelo número) deve achar o unificado
    found = await _find_lead(account.id, "5584888", db_session)
    assert found is not None
    assert found.id == survivor.id
    # E também continua achando pelo PSID do Instagram
    found_ig = await _find_lead(account.id, "PSID_IG", db_session)
    assert found_ig.id == survivor.id


# ---------------------------------------------------------------------------
# auto_merge_by_phone
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_auto_merge_by_phone_unifies(db_session):
    account, _ = await _account_and_user(db_session)
    now = datetime.now(timezone.utc)

    # lead do Instagram (mais antigo) que ganhou telefone
    ig_lead = _lead(account.id, "PSID_IG", name="Ana", phone="+5585777")
    ig_lead.captured_at = now - timedelta(days=2)
    # lead do WhatsApp (mais novo) com o mesmo telefone
    wa_lead = _lead(account.id, "5585777", name="5585777", phone="+5585777")
    wa_lead.captured_at = now
    db_session.add_all([ig_lead, wa_lead])
    await db_session.flush()

    survivor = await auto_merge_by_phone(wa_lead, db_session)

    # sobrevivente é o mais antigo (Instagram)
    assert survivor.id == ig_lead.id
    assert survivor.name == "Ana"
    assert ",5585777," in survivor.alt_handles
    # só resta um lead
    remaining = (await db_session.execute(
        select(Lead).where(Lead.account_id == account.id)
    )).scalars().all()
    assert len(remaining) == 1


@pytest.mark.asyncio
async def test_auto_merge_no_match_keeps_lead(db_session):
    account, _ = await _account_and_user(db_session)
    solo = _lead(account.id, "5586111", phone="+5586111")
    db_session.add(solo)
    await db_session.flush()

    survivor = await auto_merge_by_phone(solo, db_session)
    assert survivor.id == solo.id


# ---------------------------------------------------------------------------
# Manual merge endpoint
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_merge_endpoint(client, db_session):
    account, headers = await _account_and_user(db_session)
    ig_lead = _lead(account.id, "PSID_IG", name="Carla")
    wa_lead = _lead(account.id, "5587222", phone="+5587222")
    db_session.add_all([ig_lead, wa_lead])
    await db_session.flush()

    resp = await client.post(
        f"/api/v1/leads/{ig_lead.id}/merge",
        json={"absorbed_lead_id": wa_lead.id},
        headers=headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["id"] == ig_lead.id
    assert data["phone"] == "+5587222"

    gone = await db_session.get(Lead, wa_lead.id)
    assert gone is None


@pytest.mark.asyncio
async def test_merge_endpoint_rejects_self(client, db_session):
    account, headers = await _account_and_user(db_session)
    lead = _lead(account.id, "PSID_X")
    db_session.add(lead)
    await db_session.flush()

    resp = await client.post(
        f"/api/v1/leads/{lead.id}/merge",
        json={"absorbed_lead_id": lead.id},
        headers=headers,
    )
    assert resp.status_code == 400
