"""
Tests for the end-to-end Instagram DM flow:
  - tenant resolution by ig_business_account_id (the bug that made
    accounts connected via Instagram Login unreachable by webhooks)
  - inbound DM creates lead + conversation(channel=instagram) + message
  - echo detection via is_echo (not sender==recipient)
  - reactions update the original message instead of creating a new one
  - outbound send via /conversations/{id}/messages routes to Instagram,
    not WhatsApp, when the conversation's channel is instagram
"""
import hashlib
import hmac
import json
import uuid

import pytest
from sqlalchemy import select
from unittest.mock import ANY, AsyncMock, patch

from app.core.security import create_access_token
from app.models.account import Account
from app.models.user import User
from app.models.lead import Lead
from app.models.conversation import Conversation
from app.models.message import Message
from app.models.meta_connection import MetaConnection, PROVIDER_INSTAGRAM, STATUS_ACTIVE
from app.services.meta_token_service import encrypt_token

APP_SECRET = "test_app_secret"


@pytest.fixture(autouse=True)
def _mock_ig_profile():
    """Evita chamada de rede real ao buscar o perfil do remetente na Graph API."""
    with patch(
        "app.services.instagram_service.get_user_profile",
        new_callable=AsyncMock,
        return_value={"name": "Cliente IG", "username": "cliente_ig", "profile_pic": None},
    ):
        yield


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


def _ig_messaging_payload(ig_business_id: str, messaging_value: dict) -> dict:
    return {
        "object": "instagram",
        "entry": [{"id": ig_business_id, "messaging": [messaging_value]}],
    }


async def _ig_tenant(db_session, ig_business_id: str):
    account = Account(brand_name=f"IG {ig_business_id}")
    db_session.add(account)
    await db_session.flush()
    conn = MetaConnection(
        id=str(uuid.uuid4()),
        account_id=account.id,
        provider=PROVIDER_INSTAGRAM,
        ig_business_account_id=ig_business_id,
        meta_user_id=ig_business_id,
        access_token_encrypted=encrypt_token("fake_ig_token"),
        status=STATUS_ACTIVE,
    )
    db_session.add(conn)
    await db_session.flush()
    return account, conn


# ---------------------------------------------------------------------------
# Tenant resolution — the core bug fix
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_webhook_resolves_tenant_by_ig_business_account_id(client, db_session):
    """
    Instagram Login connections never populate MetaConnection.page_id — only
    ig_business_account_id. The webhook's entry.id for these accounts is the
    IG-scoped user id, so resolution must fall back to that column.
    """
    account, _ = await _ig_tenant(db_session, "IG_BIZ_001")

    payload = _ig_messaging_payload(
        "IG_BIZ_001",
        {
            "sender": {"id": "PSID_1"},
            "recipient": {"id": "IG_BIZ_001"},
            "timestamp": 1234567890,
            "message": {"mid": "IGMID_1", "text": "oi, quanto custa?"},
        },
    )
    resp = await _signed_post(client, payload)
    assert resp.status_code == 200

    lead = (await db_session.execute(
        select(Lead).where(Lead.account_id == account.id)
    )).scalar_one()
    assert lead.instagram_handle == "PSID_1"


# ---------------------------------------------------------------------------
# Inbound DM — creates conversation(channel=instagram) + message
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_inbound_dm_creates_instagram_conversation(client, db_session):
    account, _ = await _ig_tenant(db_session, "IG_BIZ_002")

    payload = _ig_messaging_payload(
        "IG_BIZ_002",
        {
            "sender": {"id": "PSID_2"},
            "recipient": {"id": "IG_BIZ_002"},
            "timestamp": 1234567890,
            "message": {"mid": "IGMID_2", "text": "quero saber mais"},
        },
    )
    resp = await _signed_post(client, payload)
    assert resp.status_code == 200

    conv = (await db_session.execute(
        select(Conversation).where(Conversation.tenant_id == account.id)
    )).scalar_one()
    assert conv.channel == "instagram"
    assert conv.unread_count == 1

    msg = (await db_session.execute(
        select(Message).where(Message.tenant_id == account.id)
    )).scalar_one()
    assert msg.text == "quero saber mais"
    assert msg.direction == "inbound"
    assert msg.message_id == "IGMID_2"


@pytest.mark.asyncio
async def test_inbound_dm_with_image_attachment(client, db_session):
    account, _ = await _ig_tenant(db_session, "IG_BIZ_003")

    payload = _ig_messaging_payload(
        "IG_BIZ_003",
        {
            "sender": {"id": "PSID_3"},
            "recipient": {"id": "IG_BIZ_003"},
            "timestamp": 0,
            "message": {
                "mid": "IGMID_3",
                "attachments": [{"type": "image", "payload": {"url": "https://cdn.example/img.jpg"}}],
            },
        },
    )
    resp = await _signed_post(client, payload)
    assert resp.status_code == 200

    msg = (await db_session.execute(
        select(Message).where(Message.tenant_id == account.id)
    )).scalar_one()
    assert msg.media_type == "image"
    assert msg.media_url == "https://cdn.example/img.jpg"


# ---------------------------------------------------------------------------
# Echo detection — must use is_echo, not sender==recipient
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_echo_message_is_ignored(client, db_session):
    account, _ = await _ig_tenant(db_session, "IG_BIZ_004")

    payload = _ig_messaging_payload(
        "IG_BIZ_004",
        {
            "sender": {"id": "IG_BIZ_004"},
            "recipient": {"id": "PSID_4"},
            "timestamp": 0,
            "message": {"mid": "IGMID_ECHO", "text": "resposta do agente", "is_echo": True},
        },
    )
    resp = await _signed_post(client, payload)
    assert resp.status_code == 200

    count = (await db_session.execute(
        select(Message).where(Message.tenant_id == account.id)
    )).scalars().all()
    assert len(count) == 0


# ---------------------------------------------------------------------------
# Reactions — update original message, no duplicate row
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_reaction_updates_original_message(client, db_session):
    account, _ = await _ig_tenant(db_session, "IG_BIZ_005")

    conv = Conversation(id=str(uuid.uuid4()), tenant_id=account.id, channel="instagram")
    db_session.add(conv)
    await db_session.flush()
    original = Message(
        tenant_id=account.id,
        conversation_id=conv.id,
        sender="agente",
        text="Promoção hoje!",
        direction="outbound",
        message_id="IGMID_TARGET",
    )
    db_session.add(original)
    await db_session.flush()

    payload = _ig_messaging_payload(
        "IG_BIZ_005",
        {
            "sender": {"id": "PSID_5"},
            "recipient": {"id": "IG_BIZ_005"},
            "timestamp": 0,
            "reaction": {"mid": "IGMID_TARGET", "action": "react", "emoji": "🔥"},
        },
    )
    resp = await _signed_post(client, payload)
    assert resp.status_code == 200

    await db_session.refresh(original)
    assert original.payload["customer_reaction"] == "🔥"

    count = (await db_session.execute(
        select(Message).where(Message.tenant_id == account.id)
    )).scalars().all()
    assert len(count) == 1


# ---------------------------------------------------------------------------
# Outbound send routes to Instagram when conversation channel is instagram
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_outbound_send_uses_instagram_service_for_ig_conversation(client, db_session):
    account, _ = await _ig_tenant(db_session, "IG_BIZ_006")

    user = User(
        id=str(uuid.uuid4()),
        tenant_id=account.id,
        username="agent_ig",
        password_hash="x",
        role="admin",
        is_active=True,
    )
    db_session.add(user)

    lead = Lead(
        id=str(uuid.uuid4()),
        account_id=account.id,
        instagram_handle="PSID_6",
        name="Cliente IG",
        source="manual",
        status="new",
    )
    db_session.add(lead)
    await db_session.flush()

    conv = Conversation(id=str(uuid.uuid4()), tenant_id=account.id, customer_id=lead.id, channel="instagram")
    db_session.add(conv)
    await db_session.flush()

    headers = {"Authorization": f"Bearer {create_access_token(user.id, account.id, 'admin')}"}

    with patch(
        "app.services.instagram_service.send_dm",
        new_callable=AsyncMock,
        return_value={"message_id": "IGMID_OUT_1"},
    ) as mock_send, patch(
        "app.services.whatsapp_service.send_text", new_callable=AsyncMock,
    ) as mock_wa_send:
        resp = await client.post(
            f"/api/v1/conversations/{conv.id}/messages",
            json={"text": "Oi! Como posso ajudar?", "direction": "outbound"},
            headers=headers,
        )

    assert resp.status_code == 201
    data = resp.json()
    assert data["message_id"] == "IGMID_OUT_1"
    assert data["status"] == "sent"
    mock_send.assert_called_once_with(ANY, "PSID_6", "Oi! Como posso ajudar?")
    mock_wa_send.assert_not_called()
