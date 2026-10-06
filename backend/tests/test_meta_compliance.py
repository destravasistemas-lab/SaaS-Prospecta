"""
Meta platform compliance rules:
  - WhatsApp opt-in required for templates/broadcasts; opt-out keywords honored
  - 24h window on free-form WhatsApp sends
  - Data deletion callback really deletes data and exposes a status
"""
import base64
import hashlib
import hmac
import json
import uuid
from datetime import datetime, timezone

import pytest
from sqlalchemy import select
from unittest.mock import AsyncMock, patch

from app.core.security import create_access_token
from app.models.account import Account
from app.models.conversation import Conversation
from app.models.lead import Lead
from app.models.message import Message
from app.models.meta_connection import MetaConnection, PROVIDER_WHATSAPP, STATUS_ACTIVE
from app.models.user import User
from app.services import messaging_policy
from app.services.meta_token_service import encrypt_token

from tests.test_whatsapp_flow import _signed_post, _wa_payload, _wpp_tenant

APP_SECRET = "test_app_secret"


async def _admin(db_session, account):
    user = User(id=str(uuid.uuid4()), tenant_id=account.id, username=f"{uuid.uuid4()}@t.com",
                password_hash="x", role="admin", is_active=True)
    db_session.add(user)
    await db_session.flush()
    return {"Authorization": f"Bearer {create_access_token(user.id, account.id, 'admin')}"}


def _lead(account_id: str, phone: str, opt_in: bool = False) -> Lead:
    lead = Lead(id=str(uuid.uuid4()), account_id=account_id, instagram_handle=phone,
                phone=phone, name=phone, source="manual", status="new")
    if opt_in:
        messaging_policy.mark_opt_in(lead, "manual")
    return lead


def test_keyword_detection():
    assert messaging_policy.is_opt_out("STOP")
    assert messaging_policy.is_opt_out("  Sair ")
    assert messaging_policy.is_opt_out("PARAR!")
    assert not messaging_policy.is_opt_out("quero parar de pagar caro")
    assert messaging_policy.is_opt_in("Voltar")
    assert "START" in messaging_policy.opt_out_reply("stop")
    assert "VOLTAR" in messaging_policy.opt_out_reply("sair")


@pytest.mark.asyncio
async def test_broadcast_only_reaches_opted_in_leads(client, db_session):
    account, _ = await _wpp_tenant(db_session, "PNID_BC")
    headers = await _admin(db_session, account)
    opted = _lead(account.id, "5583900000001", opt_in=True)
    not_opted = _lead(account.id, "5583900000002")
    opted_out = _lead(account.id, "5583900000003", opt_in=True)
    messaging_policy.mark_opt_out(opted_out)
    db_session.add_all([opted, not_opted, opted_out])
    await db_session.flush()

    aud = await client.get("/api/v1/whatsapp/broadcast/audience", headers=headers)
    assert aud.json() == {"count": 1, "with_phone": 3, "without_opt_in": 2}

    with patch("app.services.whatsapp_service.send_template", new_callable=AsyncMock,
               return_value={"messages": [{"id": "wamid.BC"}]}) as mock_tpl:
        resp = await client.post("/api/v1/whatsapp/broadcast",
                                 json={"template_name": "promo"}, headers=headers)
    assert resp.json()["total"] == 1
    mock_tpl.assert_called_once()
    assert mock_tpl.call_args.args[2] == "5583900000001"


@pytest.mark.asyncio
async def test_send_template_requires_opt_in(client, db_session):
    account, _ = await _wpp_tenant(db_session, "PNID_TPL")
    headers = await _admin(db_session, account)
    lead = _lead(account.id, "5583900000010")
    db_session.add(lead)
    await db_session.flush()

    with patch("app.services.whatsapp_service.send_template", new_callable=AsyncMock,
               return_value={"messages": [{"id": "wamid.T"}]}) as mock_tpl:
        resp = await client.post("/api/v1/whatsapp/send-template",
                                 json={"to": "5583900000010", "template_name": "hello"},
                                 headers={**headers, "X-Lang": "en"})
        assert resp.status_code == 422
        assert resp.json()["detail"]["code"] == "opt_in_required"
        mock_tpl.assert_not_called()

        # Agent confirms consent → recorded on the lead and template goes out
        resp = await client.post("/api/v1/whatsapp/send-template",
                                 json={"to": "5583900000010", "template_name": "hello",
                                       "opt_in_confirmed": True},
                                 headers=headers)
        assert resp.status_code == 200
        mock_tpl.assert_called_once()
    await db_session.refresh(lead)
    assert lead.whatsapp_opt_in and lead.whatsapp_opt_in_source == "manual"


@pytest.mark.asyncio
async def test_send_text_blocked_outside_window(client, db_session):
    account, _ = await _wpp_tenant(db_session, "PNID_WIN")
    headers = await _admin(db_session, account)
    with patch("app.services.whatsapp_service.send_text", new_callable=AsyncMock) as mock_send:
        resp = await client.post("/api/v1/whatsapp/send",
                                 json={"to": "5583900000020", "text": "hi"}, headers=headers)
    assert resp.status_code == 422
    assert resp.json()["detail"]["code"] == "outside_24h_window"
    mock_send.assert_not_called()


@pytest.mark.asyncio
async def test_opt_out_keyword_marks_lead_and_skips_bot(client, db_session):
    account, _ = await _wpp_tenant(db_session, "PNID_OUT")
    lead = _lead(account.id, "5583911112222", opt_in=True)
    db_session.add(lead)
    await db_session.flush()

    payload = _wa_payload("PNID_OUT", messages=[{
        "from": "5583911112222", "id": "wamid.STOP_1",
        "timestamp": str(int(datetime.now(timezone.utc).timestamp())),
        "type": "text", "text": {"body": "SAIR"},
    }])
    with patch("app.services.whatsapp_service.send_text", new_callable=AsyncMock,
               return_value={"messages": [{"id": "wamid.CONF"}]}) as mock_send, \
         patch("app.services.ai_agent.handle_inbound", new_callable=AsyncMock) as mock_ai:
        resp = await _signed_post(client, payload)
    assert resp.status_code == 200
    mock_ai.assert_not_called()
    mock_send.assert_called_once()
    assert "VOLTAR" in mock_send.call_args.args[3]

    await db_session.refresh(lead)
    assert lead.whatsapp_opt_in is False
    assert lead.whatsapp_opted_out_at is not None


def _signed_request(payload: dict) -> str:
    enc = base64.urlsafe_b64encode(json.dumps(payload).encode()).decode().rstrip("=")
    sig = hmac.new(APP_SECRET.encode(), enc.encode(), hashlib.sha256).digest()
    return base64.urlsafe_b64encode(sig).decode().rstrip("=") + "." + enc


@pytest.mark.asyncio
async def test_data_deletion_callback_deletes_and_reports_status(client, db_session):
    account = Account(brand_name="Del")
    db_session.add(account)
    await db_session.flush()
    db_session.add(MetaConnection(
        id=str(uuid.uuid4()), account_id=account.id, provider=PROVIDER_WHATSAPP,
        meta_user_id="FB_USER_1", access_token_encrypted=encrypt_token("t"), status=STATUS_ACTIVE,
    ))
    lead = Lead(id=str(uuid.uuid4()), account_id=account.id, instagram_handle="FB_USER_1",
                name="x", source="manual", status="new")
    db_session.add(lead)
    await db_session.flush()
    conv = Conversation(id=str(uuid.uuid4()), tenant_id=account.id, customer_id=lead.id)
    db_session.add(conv)
    await db_session.flush()
    db_session.add(Message(tenant_id=account.id, conversation_id=conv.id, sender="x",
                           text="hi", direction="inbound", status="delivered"))
    await db_session.flush()

    resp = await client.post(
        "/api/v1/privacy/data-deletion",
        data={"signed_request": _signed_request({"algorithm": "HMAC-SHA256", "user_id": "FB_USER_1"})},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert "/data-deletion?code=" in body["url"]

    assert (await db_session.execute(
        select(MetaConnection).where(MetaConnection.meta_user_id == "FB_USER_1")
    )).first() is None
    assert (await db_session.execute(select(Lead).where(Lead.id == lead.id))).first() is None

    status = await client.get("/api/v1/privacy/data-deletion-status",
                              params={"id": body["confirmation_code"]})
    assert status.status_code == 200
    assert status.json()["status"] == "completed"


@pytest.mark.asyncio
async def test_data_deletion_rejects_bad_signature(client):
    resp = await client.post("/api/v1/privacy/data-deletion", data={"signed_request": "bad.sig"})
    assert resp.status_code == 400
