"""
Tests for the end-to-end WhatsApp flow:
  - webhook inbound handling (text, media, location, reaction, status errors)
  - 24h session-window guard on outbound free-form messages
"""
import hashlib
import hmac
import json
import uuid
from datetime import datetime, timezone, timedelta

import pytest
from sqlalchemy import select
from unittest.mock import AsyncMock, patch

from app.core.security import create_access_token
from app.models.account import Account
from app.models.user import User
from app.models.lead import Lead
from app.models.conversation import Conversation
from app.models.message import Message
from app.models.meta_connection import MetaConnection, PROVIDER_WHATSAPP, STATUS_ACTIVE
from app.services.meta_token_service import encrypt_token

APP_SECRET = "test_app_secret"


def _make_signature(body: bytes) -> str:
    sig = hmac.new(APP_SECRET.encode(), body, hashlib.sha256).hexdigest()
    return f"sha256={sig}"


async def _signed_post(client, payload: dict):
    body = json.dumps(payload).encode()
    return await client.post(
        "/api/v1/webhook/meta",
        content=body,
        headers={
            "Content-Type": "application/json",
            "X-Hub-Signature-256": _make_signature(body),
        },
    )


def _wa_payload(phone_number_id: str, messages=None, statuses=None, contacts=None) -> dict:
    value: dict = {
        "messaging_product": "whatsapp",
        "metadata": {"display_phone_number": "5583", "phone_number_id": phone_number_id},
    }
    if contacts:
        value["contacts"] = contacts
    if messages:
        value["messages"] = messages
    if statuses:
        value["statuses"] = statuses
    return {
        "object": "whatsapp_business_account",
        "entry": [{"id": "WABA_ENTRY", "changes": [{"field": "messages", "value": value}]}],
    }


async def _wpp_tenant(db_session, phone_number_id: str):
    account = Account(brand_name=f"WPP {phone_number_id}")
    db_session.add(account)
    await db_session.flush()
    conn = MetaConnection(
        id=str(uuid.uuid4()),
        account_id=account.id,
        provider=PROVIDER_WHATSAPP,
        phone_number_id=phone_number_id,
        phone_number="+55 83 99999-9999",
        waba_id="WABA_1",
        access_token_encrypted=encrypt_token("fake_token"),
        status=STATUS_ACTIVE,
    )
    db_session.add(conn)
    await db_session.flush()
    return account, conn


# ---------------------------------------------------------------------------
# Webhook — inbound messages
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_inbound_text_creates_lead_conversation_message(client, db_session):
    account, _ = await _wpp_tenant(db_session, "PNID_TEXT")

    payload = _wa_payload(
        "PNID_TEXT",
        contacts=[{"profile": {"name": "João"}, "wa_id": "5583911110001"}],
        messages=[{
            "from": "5583911110001",
            "id": "wamid.IN_1",
            "timestamp": str(int(datetime.now(timezone.utc).timestamp())),
            "type": "text",
            "text": {"body": "Olá, quero um orçamento"},
        }],
    )
    resp = await _signed_post(client, payload)
    assert resp.status_code == 200

    lead = (await db_session.execute(
        select(Lead).where(Lead.account_id == account.id)
    )).scalar_one()
    assert lead.phone is not None

    conv = (await db_session.execute(
        select(Conversation).where(Conversation.tenant_id == account.id)
    )).scalar_one()
    assert conv.unread_count == 1

    msg = (await db_session.execute(
        select(Message).where(Message.tenant_id == account.id)
    )).scalar_one()
    assert msg.direction == "inbound"
    assert msg.text == "Olá, quero um orçamento"
    assert msg.message_id == "wamid.IN_1"


@pytest.mark.asyncio
async def test_inbound_image_stores_proxy_media_url(client, db_session):
    account, _ = await _wpp_tenant(db_session, "PNID_IMG")

    payload = _wa_payload(
        "PNID_IMG",
        messages=[{
            "from": "5583911110002",
            "id": "wamid.IN_IMG",
            "timestamp": "0",
            "type": "image",
            "image": {"id": "MEDIA_123", "mime_type": "image/jpeg", "caption": "olha isso"},
        }],
    )
    resp = await _signed_post(client, payload)
    assert resp.status_code == 200

    msg = (await db_session.execute(
        select(Message).where(Message.tenant_id == account.id)
    )).scalar_one()
    assert msg.media_type == "image"
    assert msg.media_url == "/whatsapp/media/MEDIA_123"
    assert msg.text == "olha isso"


@pytest.mark.asyncio
async def test_inbound_location_renders_maps_link(client, db_session):
    account, _ = await _wpp_tenant(db_session, "PNID_LOC")

    payload = _wa_payload(
        "PNID_LOC",
        messages=[{
            "from": "5583911110003",
            "id": "wamid.IN_LOC",
            "timestamp": "0",
            "type": "location",
            "location": {"latitude": -7.115, "longitude": -34.861, "name": "João Pessoa"},
        }],
    )
    resp = await _signed_post(client, payload)
    assert resp.status_code == 200

    msg = (await db_session.execute(
        select(Message).where(Message.tenant_id == account.id)
    )).scalar_one()
    assert "João Pessoa" in msg.text
    assert "maps.google.com" in msg.text


@pytest.mark.asyncio
async def test_inbound_reaction_updates_original_message(client, db_session):
    account, _ = await _wpp_tenant(db_session, "PNID_REACT")

    conv = Conversation(id=str(uuid.uuid4()), tenant_id=account.id)
    db_session.add(conv)
    await db_session.flush()
    original = Message(
        tenant_id=account.id,
        conversation_id=conv.id,
        sender="agente",
        text="Oferta especial!",
        direction="outbound",
        message_id="wamid.OUT_TARGET",
    )
    db_session.add(original)
    await db_session.flush()

    payload = _wa_payload(
        "PNID_REACT",
        messages=[{
            "from": "5583911110004",
            "id": "wamid.IN_REACT",
            "timestamp": "0",
            "type": "reaction",
            "reaction": {"message_id": "wamid.OUT_TARGET", "emoji": "👍"},
        }],
    )
    resp = await _signed_post(client, payload)
    assert resp.status_code == 200

    await db_session.refresh(original)
    assert original.payload["customer_reaction"] == "👍"

    # Reação não cria mensagem nova no thread
    count = (await db_session.execute(
        select(Message).where(Message.tenant_id == account.id)
    )).scalars().all()
    assert len(count) == 1


@pytest.mark.asyncio
async def test_failed_status_stores_error_detail(client, db_session):
    account, _ = await _wpp_tenant(db_session, "PNID_FAIL")

    conv = Conversation(id=str(uuid.uuid4()), tenant_id=account.id)
    db_session.add(conv)
    await db_session.flush()
    msg = Message(
        tenant_id=account.id,
        conversation_id=conv.id,
        sender="agente",
        text="mensagem que vai falhar",
        direction="outbound",
        message_id="wamid.OUT_FAIL",
    )
    db_session.add(msg)
    await db_session.flush()

    payload = _wa_payload(
        "PNID_FAIL",
        statuses=[{
            "id": "wamid.OUT_FAIL",
            "status": "failed",
            "errors": [{
                "code": 131047,
                "title": "Re-engagement message",
                "error_data": {"details": "Janela de 24h expirada."},
            }],
        }],
    )
    resp = await _signed_post(client, payload)
    assert resp.status_code == 200

    await db_session.refresh(msg)
    assert msg.status == "failed"
    assert msg.payload["error"] == "Janela de 24h expirada."


# ---------------------------------------------------------------------------
# Janela de 24h — guarda no envio de mensagem livre
# ---------------------------------------------------------------------------

async def _agent_setup(db_session, phone_number_id: str, last_inbound_age: timedelta | None):
    """Tenant + user autenticado + conversa com (ou sem) mensagem inbound recente."""
    account, conn = await _wpp_tenant(db_session, phone_number_id)

    user = User(
        id=str(uuid.uuid4()),
        tenant_id=account.id,
        username=f"agent_{phone_number_id}",
        password_hash="x",
        role="admin",
        is_active=True,
    )
    db_session.add(user)

    lead = Lead(
        id=str(uuid.uuid4()),
        account_id=account.id,
        instagram_handle="5583900000009",
        phone="+5583900000009",
        name="Cliente",
        source="manual",
        status="new",
    )
    db_session.add(lead)
    await db_session.flush()

    conv = Conversation(id=str(uuid.uuid4()), tenant_id=account.id, customer_id=lead.id)
    db_session.add(conv)
    await db_session.flush()

    if last_inbound_age is not None:
        inbound = Message(
            tenant_id=account.id,
            conversation_id=conv.id,
            sender="5583900000009",
            text="oi",
            direction="inbound",
            wa_id="5583900000009",
            message_id="wamid.WINDOW",
            created_at=datetime.now(timezone.utc) - last_inbound_age,
        )
        db_session.add(inbound)
        await db_session.flush()

    headers = {"Authorization": f"Bearer {create_access_token(user.id, account.id, 'admin')}"}
    return conv, headers


@pytest.mark.asyncio
async def test_send_blocked_outside_24h_window(client, db_session):
    conv, headers = await _agent_setup(db_session, "PNID_WIN_OLD", timedelta(hours=25))

    resp = await client.post(
        f"/api/v1/conversations/{conv.id}/messages",
        json={"text": "tentativa fora da janela", "direction": "outbound"},
        headers=headers,
    )
    assert resp.status_code == 422
    assert resp.json()["detail"]["code"] == "outside_24h_window"


@pytest.mark.asyncio
async def test_send_allowed_inside_24h_window(client, db_session):
    conv, headers = await _agent_setup(db_session, "PNID_WIN_OK", timedelta(hours=1))

    with patch(
        "app.services.whatsapp_service.send_text",
        new_callable=AsyncMock,
        return_value={"messages": [{"id": "wamid.SENT_OK"}]},
    ) as mock_send:
        resp = await client.post(
            f"/api/v1/conversations/{conv.id}/messages",
            json={"text": "dentro da janela", "direction": "outbound"},
            headers=headers,
        )

    assert resp.status_code == 201
    data = resp.json()
    assert data["status"] == "sent"
    assert data["message_id"] == "wamid.SENT_OK"
    assert data["is_within_24h_window"] is True
    mock_send.assert_called_once()


@pytest.mark.asyncio
async def test_send_blocked_when_customer_never_replied(client, db_session):
    conv, headers = await _agent_setup(db_session, "PNID_WIN_NEVER", None)

    resp = await client.post(
        f"/api/v1/conversations/{conv.id}/messages",
        json={"text": "primeira abordagem livre", "direction": "outbound"},
        headers=headers,
    )
    assert resp.status_code == 422
    assert resp.json()["detail"]["code"] == "outside_24h_window"
