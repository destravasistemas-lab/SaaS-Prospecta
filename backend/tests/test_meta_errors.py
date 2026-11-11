"""
Meta rejections must surface as errors (never a fake "sent"), and successful
sends must persist the wamid used to match webhook status updates.
"""
import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy import select

from app.core.security import create_access_token
from app.models.conversation import Conversation
from app.models.lead import Lead
from app.models.message import Message
from app.models.user import User
from app.services import messaging_policy

from tests.test_whatsapp_flow import _wpp_tenant

NOT_REGISTERED = {"error": {"message": "(#133010) Account not registered", "type": "OAuthException", "code": 133010}}


async def _admin_with_lead(db_session, pnid: str, phone: str):
    account, conn = await _wpp_tenant(db_session, pnid)
    user = User(id=str(uuid.uuid4()), tenant_id=account.id, username=f"{uuid.uuid4()}@t.com",
                password_hash="x", role="admin", is_active=True)
    lead = Lead(id=str(uuid.uuid4()), account_id=account.id, instagram_handle=phone,
                phone=phone, name="Ana", source="manual", status="new")
    messaging_policy.mark_opt_in(lead, "manual")
    db_session.add_all([user, lead])
    await db_session.flush()
    headers = {"Authorization": f"Bearer {create_access_token(user.id, account.id, 'admin')}"}
    return account, conn, lead, headers


@pytest.mark.asyncio
async def test_send_template_meta_rejection_returns_502(client, db_session):
    account, _, _, headers = await _admin_with_lead(db_session, "PNID_ERR1", "5583977770001")
    with patch("app.services.whatsapp_service.send_template", new_callable=AsyncMock, return_value=NOT_REGISTERED):
        resp = await client.post("/api/v1/whatsapp/send-template",
                                 json={"to": "5583977770001", "template_name": "hello"},
                                 headers={**headers, "X-Lang": "en"})
    assert resp.status_code == 502
    detail = resp.json()["detail"]
    assert detail["code"] == "meta_error" and detail["meta_code"] == 133010
    assert "Register number" in detail["message"]
    msgs = (await db_session.execute(select(Message).where(Message.tenant_id == account.id))).scalars().all()
    assert msgs == []


@pytest.mark.asyncio
async def test_send_template_success_persists_wamid(client, db_session):
    account, _, lead, headers = await _admin_with_lead(db_session, "PNID_ERR2", "5583977770002")
    conv = Conversation(id=str(uuid.uuid4()), tenant_id=account.id, customer_id=lead.id)
    db_session.add(conv)
    await db_session.flush()
    with patch("app.services.whatsapp_service.send_template", new_callable=AsyncMock,
               return_value={"messages": [{"id": "wamid.OK123"}]}):
        resp = await client.post("/api/v1/whatsapp/send-template",
                                 json={"to": "5583977770002", "template_name": "hello", "conversation_id": conv.id},
                                 headers=headers)
    assert resp.status_code == 200 and resp.json()["wamid"] == "wamid.OK123"
    msg = (await db_session.execute(select(Message).where(Message.conversation_id == conv.id))).scalar_one()
    assert msg.message_id == "wamid.OK123"


@pytest.mark.asyncio
async def test_chat_send_meta_rejection_returns_502_and_stores_nothing(client, db_session):
    account, _, lead, headers = await _admin_with_lead(db_session, "PNID_ERR3", "5583977770003")
    conv = Conversation(id=str(uuid.uuid4()), tenant_id=account.id, customer_id=lead.id, channel="whatsapp")
    db_session.add(conv)
    await db_session.flush()
    db_session.add(Message(tenant_id=account.id, conversation_id=conv.id, sender=lead.phone, text="oi",
                           direction="inbound", wa_id=lead.phone, status="delivered",
                           created_at=datetime.now(timezone.utc)))
    await db_session.flush()
    with patch("app.services.whatsapp_service.send_text", new_callable=AsyncMock, return_value=NOT_REGISTERED):
        resp = await client.post(f"/api/v1/conversations/{conv.id}/messages",
                                 json={"text": "Olá!", "direction": "outbound"}, headers=headers)
    assert resp.status_code == 502
    assert resp.json()["detail"]["meta_code"] == 133010
    outbound = (await db_session.execute(
        select(Message).where(Message.conversation_id == conv.id, Message.direction == "outbound")
    )).scalars().all()
    assert outbound == []


@pytest.mark.asyncio
async def test_broadcast_counts_meta_rejections_as_failed(client, db_session):
    _, _, _, headers = await _admin_with_lead(db_session, "PNID_ERR4", "5583977770004")
    with patch("app.services.whatsapp_service.send_template", new_callable=AsyncMock, return_value=NOT_REGISTERED):
        resp = await client.post("/api/v1/whatsapp/broadcast", json={"template_name": "promo"}, headers=headers)
    # Account-level error: the broadcast stops and reports it instead of "succeeding"
    assert resp.status_code == 502
    assert resp.json()["detail"]["meta_code"] == 133010


@pytest.mark.asyncio
async def test_broadcast_reports_per_contact_failures(client, db_session):
    _, _, _, headers = await _admin_with_lead(db_session, "PNID_ERR6", "5583977770006")
    per_contact = {"error": {"message": "Recipient not in allowed list", "code": 131030}}
    with patch("app.services.whatsapp_service.send_template", new_callable=AsyncMock, return_value=per_contact):
        resp = await client.post("/api/v1/whatsapp/broadcast", json={"template_name": "promo"}, headers=headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["sent"] == 0 and body["failed"] == 1 and body["error"]


@pytest.mark.asyncio
async def test_register_number(client, db_session):
    _, conn, _, headers = await _admin_with_lead(db_session, "PNID_ERR5", "5583977770005")
    with patch("app.services.whatsapp_service.register_phone_number", new_callable=AsyncMock,
               return_value={"success": True}) as mock_reg:
        ok = await client.post("/api/v1/whatsapp/register", json={"pin": "123456"}, headers=headers)
    assert ok.status_code == 200 and ok.json()["success"] is True
    assert mock_reg.call_args.args[1:] == ("PNID_ERR5", "123456")

    bad_pin = await client.post("/api/v1/whatsapp/register", json={"pin": "12ab"}, headers=headers)
    assert bad_pin.status_code == 422

    with patch("app.services.whatsapp_service.register_phone_number", new_callable=AsyncMock,
               return_value={"error": {"message": "PIN mismatch", "code": 133005}}):
        mismatch = await client.post("/api/v1/whatsapp/register", json={"pin": "654321"}, headers=headers)
    assert mismatch.status_code == 502
    assert mismatch.json()["detail"]["meta_code"] == 133005
