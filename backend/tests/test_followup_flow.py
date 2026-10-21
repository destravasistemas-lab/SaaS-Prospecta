"""
Automatic WhatsApp follow-up:
  - sends the follow-up template after N days without reply (opted-in only)
  - never twice for the same original message, never a follow-up of a follow-up
  - respects reply, opt-out and the sending hours window
"""
import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy import select

from app.core.security import create_access_token
from app.models.conversation import Conversation
from app.models.followup import FollowUpDispatch, FollowUpRule
from app.models.lead import Lead
from app.models.message import Message
from app.models.user import User
from app.services import messaging_policy
from app.services.followup_service import run_due_followups

from tests.test_whatsapp_flow import _wpp_tenant


async def _setup(db_session, pnid: str, *, opt_in=True, sent_days_ago=4, phone="5583988887777"):
    account, conn = await _wpp_tenant(db_session, pnid)
    lead = Lead(id=str(uuid.uuid4()), account_id=account.id, instagram_handle=phone,
                phone=phone, name="Ana", source="manual", status="new")
    if opt_in:
        messaging_policy.mark_opt_in(lead, "manual")
    db_session.add(lead)
    await db_session.flush()
    conv = Conversation(id=str(uuid.uuid4()), tenant_id=account.id, customer_id=lead.id)
    db_session.add(conv)
    await db_session.flush()
    original = Message(
        tenant_id=account.id, conversation_id=conv.id, sender="admin", text="[template:promo]",
        direction="outbound", wa_id=phone, status="sent", message_id="wamid.ORIG",
        template_name="promo", is_within_24h_window=False,
        created_at=datetime.now(timezone.utc) - timedelta(days=sent_days_ago),
    )
    db_session.add(original)
    rule = FollowUpRule(account_id=account.id, name="Lembrete", delay_days=3,
                        template_name="lembrete", template_language="pt_BR",
                        variables=["Ana"], send_hour_start=0, send_hour_end=24)
    db_session.add(rule)
    await db_session.flush()
    return account, conv, lead, original, rule


def _mock_send():
    return patch("app.services.whatsapp_service.send_template", new_callable=AsyncMock,
                 return_value={"messages": [{"id": "wamid.FU"}]})


@pytest.mark.asyncio
async def test_sends_followup_once_and_never_chains(db_session):
    account, conv, lead, original, rule = await _setup(db_session, "PNID_FU1")

    with _mock_send() as mock_send:
        assert await run_due_followups(db_session) == 1
        assert mock_send.call_args.args[3] == "lembrete"
        assert mock_send.call_args.args[2] == "5583988887777"

        # Second run: original already handled; the follow-up itself is not followed up
        future = datetime.now(timezone.utc) + timedelta(days=5)
        assert await run_due_followups(db_session, now=future) == 0
        assert mock_send.call_count == 1

    fu = (await db_session.execute(
        select(Message).where(Message.conversation_id == conv.id, Message.sender == "followup")
    )).scalar_one()
    assert fu.template_name == "lembrete"
    dispatch = (await db_session.execute(select(FollowUpDispatch))).scalars().all()
    assert [d.status for d in dispatch if d.account_id == account.id] == ["sent"]


@pytest.mark.asyncio
async def test_no_followup_when_customer_replied(db_session):
    account, conv, lead, original, rule = await _setup(db_session, "PNID_FU2", phone="5583988880002")
    db_session.add(Message(
        tenant_id=account.id, conversation_id=conv.id, sender=lead.phone, text="oi",
        direction="inbound", wa_id=lead.phone, status="delivered",
        created_at=datetime.now(timezone.utc) - timedelta(days=2),
    ))
    await db_session.flush()
    with _mock_send() as mock_send:
        assert await run_due_followups(db_session) == 0
        mock_send.assert_not_called()


@pytest.mark.asyncio
async def test_no_followup_before_delay(db_session):
    await _setup(db_session, "PNID_FU3", sent_days_ago=1, phone="5583988880003")
    with _mock_send() as mock_send:
        assert await run_due_followups(db_session) == 0
        mock_send.assert_not_called()


@pytest.mark.asyncio
async def test_opted_out_contact_is_skipped(db_session):
    account, conv, lead, original, rule = await _setup(db_session, "PNID_FU4", phone="5583988880004")
    messaging_policy.mark_opt_out(lead)
    await db_session.flush()
    with _mock_send() as mock_send:
        assert await run_due_followups(db_session) == 0
        mock_send.assert_not_called()
    d = (await db_session.execute(
        select(FollowUpDispatch).where(FollowUpDispatch.account_id == account.id)
    )).scalar_one()
    assert d.status == "skipped" and d.detail == "opted_out"


@pytest.mark.asyncio
async def test_respects_sending_hours(db_session):
    account, conv, lead, original, rule = await _setup(db_session, "PNID_FU5", phone="5583988880005")
    rule.send_hour_start, rule.send_hour_end = 9, 20
    await db_session.flush()
    # 06:00 UTC = 03:00 in Brasília → outside the window
    night = datetime.now(timezone.utc).replace(hour=6, minute=0, second=0, microsecond=0)
    with _mock_send() as mock_send:
        assert await run_due_followups(db_session, now=night) == 0
        mock_send.assert_not_called()


@pytest.mark.asyncio
async def test_rule_api_requires_approved_template(client, db_session):
    account, conn = await _wpp_tenant(db_session, "PNID_FU6")
    conn.meta_templates = [
        {"name": "lembrete", "status": "APPROVED", "language": "pt_BR"},
        {"name": "rascunho", "status": "PENDING", "language": "pt_BR"},
    ]
    user = User(id=str(uuid.uuid4()), tenant_id=account.id, username="adm@fu.com",
                password_hash="x", role="admin", is_active=True)
    db_session.add(user)
    await db_session.flush()
    headers = {"Authorization": f"Bearer {create_access_token(user.id, account.id, 'admin')}"}

    bad = await client.post("/api/v1/whatsapp/followup-rules",
                            json={"name": "x", "template_name": "rascunho"}, headers=headers)
    assert bad.status_code == 422

    ok = await client.post("/api/v1/whatsapp/followup-rules",
                           json={"name": "Lembrete 3 dias", "template_name": "lembrete", "delay_days": 3},
                           headers=headers)
    assert ok.status_code == 201
    rule_id = ok.json()["id"]

    listed = await client.get("/api/v1/whatsapp/followup-rules", headers=headers)
    assert [r["id"] for r in listed.json()] == [rule_id]
    assert listed.json()[0]["sent_count"] == 0

    deleted = await client.delete(f"/api/v1/whatsapp/followup-rules/{rule_id}", headers=headers)
    assert deleted.status_code == 204
