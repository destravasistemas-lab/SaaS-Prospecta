"""
Notificações no celular (Web Push): criptografia (RFC 8291), VAPID (RFC 8292),
rotas, quem recebe (silenciar todos / contato / atendente), webhook de mensagem
nova e lead interessado marcado pela IA.
"""
import base64
import json
import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

import pytest
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.asymmetric.utils import encode_dss_signature

from app.core import redis as redis_mod
from app.core.config import settings
from app.models.conversation import Conversation
from app.models.lead import Lead
from app.models.push import ConversationMute, NotificationPref, PushSubscription
from app.models.user import User
from app.services import ai_agent, push_service

from tests.test_ai_platform import _conversation, _quiet, _send_ok
from tests.test_whatsapp_flow import _signed_post, _wa_payload, _wpp_tenant


def _b64u(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode()


@pytest.fixture(autouse=True)
def vapid(monkeypatch):
    key = ec.generate_private_key(ec.SECP256R1())
    monkeypatch.setattr(settings, "vapid_private_key", _b64u(key.private_numbers().private_value.to_bytes(32, "big")))
    monkeypatch.setattr(settings, "vapid_public_key", _b64u(key.public_key().public_bytes(
        serialization.Encoding.X962, serialization.PublicFormat.UncompressedPoint)))
    monkeypatch.setattr(settings, "gemini_api_keys", "KEY_A")
    push_service._jwt_cache.clear()
    redis_mod._memory.clear()
    yield
    redis_mod._memory.clear()


@pytest.fixture
def sent(monkeypatch):
    """Captura os envios em vez de chamar o serviço de push do navegador."""
    calls: list[dict] = []
    monkeypatch.setattr(push_service, "_spawn",
                        lambda targets, payload, urgency: calls.append(
                            {"targets": targets, "payload": payload, "urgency": urgency}))
    return calls


async def _user(db_session, tenant_id: str) -> User:
    user = User(id=str(uuid.uuid4()), tenant_id=tenant_id, username=f"{uuid.uuid4()}@t.com",
                password_hash="x", role="admin", is_active=True)
    db_session.add(user)
    await db_session.flush()
    return user


def _sub(user: User) -> PushSubscription:
    return PushSubscription(user_id=user.id, tenant_id=user.tenant_id,
                            endpoint=f"https://fcm.googleapis.com/fcm/send/{uuid.uuid4()}",
                            p256dh="B" + "A" * 86, auth="AAAAAAAAAAAAAAAAAAAAAA")


# ---------------------------------------------------------------------------
# Criptografia e VAPID
# ---------------------------------------------------------------------------

def test_encrypt_matches_rfc8291_example():
    d = push_service.b64u_decode
    as_private = ec.derive_private_key(
        int.from_bytes(d("yfWPiYE-n46HLnH0KqZOF1fJJU3MYrct3AELtAQ-oRw"), "big"), ec.SECP256R1())
    body = push_service.encrypt(
        b"When I grow up, I want to be a watermelon",
        "BCVxsr7N_eNgVRqvHtD0zTZsEc6-VV-JvLexhqUzORcxaOzi6-AYWXvTBHm4bjyPjs7Vd8pZGH6SRpkNtoIAiw4",
        "BTBZMqHH6r4Tts7J_aSIgg",
        salt=d("DGv6ra1nlYgDCS1FRnbzlw"), as_private=as_private,
    )
    assert push_service.b64u(body) == (
        "DGv6ra1nlYgDCS1FRnbzlwAAEABBBP4z9KsN6nGRTbVYI_c7VJSPQTBtkgcy27mlmlMoZIIgDll6e3vCYLocInmYWAmS6TlzAC8wEqKK6PBru3jl7A_"
        "yl95bQpu6cVPTpK4Mqgkf1CXztLVBSt2Ks3oZwbuwXPXLWyouBWLVWGNWQexSgSxsj_Qulcy4a-fN"
    )


def test_vapid_header_is_signed_for_the_push_service():
    header = push_service.vapid_authorization("https://fcm.googleapis.com/fcm/send/abc")
    token = header.split("t=")[1].split(",")[0]
    assert header.endswith(f"k={settings.vapid_public_key}")
    head, claims, sig = token.split(".")
    payload = json.loads(push_service.b64u_decode(claims))
    assert payload["aud"] == "https://fcm.googleapis.com" and payload["sub"].startswith("mailto:")
    raw = push_service.b64u_decode(sig)
    public = ec.EllipticCurvePublicKey.from_encoded_point(
        ec.SECP256R1(), push_service.b64u_decode(settings.vapid_public_key))
    public.verify(encode_dss_signature(int.from_bytes(raw[:32], "big"), int.from_bytes(raw[32:], "big")),
                  f"{head}.{claims}".encode(), ec.ECDSA(hashes.SHA256()))


# ---------------------------------------------------------------------------
# Rotas
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_subscribe_prefs_and_mute_routes(client, db_session, make_user):
    tid, headers = await make_user()
    other_tid, _ = await make_user()
    conv = Conversation(id=str(uuid.uuid4()), tenant_id=tid)
    other_conv = Conversation(id=str(uuid.uuid4()), tenant_id=other_tid)
    db_session.add_all([conv, other_conv])
    await db_session.flush()

    prefs = (await client.get("/api/v1/push/prefs", headers=headers)).json()
    assert prefs["push_enabled"] and prefs["public_key"] == settings.vapid_public_key and prefs["devices"] == 0

    sub = {"endpoint": "https://fcm.googleapis.com/fcm/send/xyz", "keys": {"p256dh": "B" + "A" * 86, "auth": "A" * 22}}
    assert (await client.post("/api/v1/push/subscribe", json=sub, headers=headers)).json()["devices"] == 1
    assert (await client.post("/api/v1/push/subscribe", json=sub, headers=headers)).json()["devices"] == 1

    prefs = (await client.put("/api/v1/push/prefs", json={"messages_enabled": False}, headers=headers)).json()
    assert prefs["messages_enabled"] is False and prefs["interest_enabled"] is True

    await client.put(f"/api/v1/push/mutes/{conv.id}", json={"muted": True}, headers=headers)
    assert conv.id in (await client.get("/api/v1/push/prefs", headers=headers)).json()["muted_conversation_ids"]
    await client.put(f"/api/v1/push/mutes/{conv.id}", json={"muted": False}, headers=headers)
    assert (await client.get("/api/v1/push/prefs", headers=headers)).json()["muted_conversation_ids"] == []
    assert (await client.put(f"/api/v1/push/mutes/{other_conv.id}", json={"muted": True},
                             headers=headers)).status_code == 404

    out = await client.post("/api/v1/push/unsubscribe", json={"endpoint": sub["endpoint"]}, headers=headers)
    assert out.json()["devices"] == 0


@pytest.mark.asyncio
async def test_subscribe_without_server_keys_is_refused(client, make_user, monkeypatch):
    monkeypatch.setattr(settings, "vapid_private_key", "")
    _, headers = await make_user()
    sub = {"endpoint": "https://fcm.googleapis.com/fcm/send/x", "keys": {"p256dh": "B" + "A" * 86, "auth": "A" * 22}}
    assert (await client.post("/api/v1/push/subscribe", json=sub, headers=headers)).status_code == 503


# ---------------------------------------------------------------------------
# Quem recebe
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_mute_all_mute_contact_assignee_and_interest(db_session, sent):
    account, _ = await _wpp_tenant(db_session, "PN_PUSH1")
    a = await _user(db_session, account.id)
    b = await _user(db_session, account.id)
    c = await _user(db_session, account.id)
    db_session.add_all([_sub(a), _sub(b), _sub(c)])
    conv = Conversation(id=str(uuid.uuid4()), tenant_id=account.id)
    db_session.add(conv)
    await db_session.flush()

    assert await push_service.notify_new_message(db_session, conv=conv, title="Maria · WhatsApp", text="Oi") == 3
    # Rajada do mesmo cliente: um aviso só
    assert await push_service.notify_new_message(db_session, conv=conv, title="x", text="Oi de novo") == 0

    redis_mod._memory.clear()
    db_session.add(ConversationMute(user_id=a.id, conversation_id=conv.id))       # A silenciou o contato
    db_session.add(NotificationPref(user_id=b.id, messages_enabled=False))         # B silenciou todos
    await db_session.flush()
    assert await push_service.notify_new_message(db_session, conv=conv, title="x", text="Oi") == 1

    # Lead interessado passa por cima dos silêncios de mensagem
    assert await push_service.notify_interest(db_session, conv=conv, title="🔥", text="me manda a tabela") == 3
    assert sent[-1]["urgency"] == "high" and sent[-1]["payload"]["kind"] == "interest"

    # Conversa com atendente: o aviso de mensagem vai só para ele
    redis_mod._memory.clear()
    conv.atendente_id = c.id
    await db_session.flush()
    assert await push_service.notify_new_message(db_session, conv=conv, title="x", text="Oi") == 1
    assert sent[-1]["targets"] == [push_service.Target(*(await _endpoint_of(db_session, c)))]


async def _endpoint_of(db_session, user: User):
    from sqlalchemy import select
    s = (await db_session.execute(select(PushSubscription).where(PushSubscription.user_id == user.id))).scalar_one()
    return s.endpoint, s.p256dh, s.auth


# ---------------------------------------------------------------------------
# Webhook e IA
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_inbound_whatsapp_message_notifies(client, db_session, sent):
    account, _ = await _wpp_tenant(db_session, "PN_PUSH2")
    user = await _user(db_session, account.id)
    db_session.add(_sub(user))
    await db_session.flush()

    await _signed_post(client, _wa_payload(
        "PN_PUSH2",
        contacts=[{"profile": {"name": "Maria Lima"}, "wa_id": "5583922220001"}],
        messages=[{"from": "5583922220001", "id": "wamid.PUSH_IN", "type": "text",
                   "timestamp": str(int(datetime.now(timezone.utc).timestamp())),
                   "text": {"body": "Oi, vocês abrem sábado?"}}],
    ))
    assert len(sent) == 1
    payload = sent[0]["payload"]
    assert payload["kind"] == "message" and payload["title"] == "Maria Lima · WhatsApp"
    assert payload["body"] == "Oi, vocês abrem sábado?" and payload["url"].startswith("/app/whatsapp?conv=")


def test_split_interest():
    assert ai_agent.split_interest("Claro! Já te passo.\n[[LEAD_INTERESSADO]]") == ("Claro! Já te passo.", True)
    assert ai_agent.split_interest("[[ lead interessado ]]") == (ai_agent.INTEREST_REPLY, True)
    assert ai_agent.split_interest("Bom dia!") == ("Bom dia!", False)


@pytest.mark.asyncio
async def test_ai_marks_interested_lead_and_notifies(db_session, sent):
    account, _, cfg, conv = await _conversation(db_session, "PN_PUSH3", own_key=True)
    cfg.handoff_rules = "pediu a tabela de preços"
    lead = Lead(id=str(uuid.uuid4()), account_id=account.id, instagram_handle="5583999990000",
                phone="5583999990000", name="João Silva", source="manual", status="new")
    db_session.add(lead)
    conv.customer_id = lead.id
    user = await _user(db_session, account.id)
    db_session.add(_sub(user))
    await db_session.flush()

    q = _quiet()
    with q[0], q[1], q[2], _send_ok() as send, patch(
        "app.services.gemini_service.generate_content", new_callable=AsyncMock,
        return_value=("Te mando já! Um atendente vai continuar com você.\n[[LEAD_INTERESSADO]]", 500),
    ) as gen:
        await ai_agent.reply_to_conversation(db_session, account.id, conv.id)

    system_prompt = gen.call_args.args[1]
    assert "[Lead interessado]" in system_prompt and "pediu a tabela de preços" in system_prompt
    assert send.call_args.args[3] == "Te mando já! Um atendente vai continuar com você."
    assert conv.bot_active is False and conv.atendimento_status == "aguardando"
    assert lead.status == "qualified"
    assert sent and sent[-1]["payload"]["title"] == "🔥 Lead interessado: João Silva"
    assert sent[-1]["payload"]["body"] == "Quanto custa?"
