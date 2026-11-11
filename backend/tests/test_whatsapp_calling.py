"""
Chamadas de voz do WhatsApp: webhook `calls` (duplicado, fora de ordem, atrasado),
quem toca, quem atende, isolamento entre tenants e o que nunca pode vazar (SDP, token).
"""
import json
import logging
import time
import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, patch

import httpx
import pytest
from sqlalchemy import select

from app.core.config import settings
from app.core.modules import users_with_module
from app.core.security import create_access_token
from app.core.ws_manager import ConnectionManager, ws_manager
from app.main import _RedactSecretsFilter
from app.models.account import Account
from app.models.conversation import Conversation
from app.models.lead import Lead
from app.models.message import Message
from app.models.meta_connection import MetaConnection, PROVIDER_WHATSAPP, STATUS_ACTIVE
from app.models.user import User
from app.models.whatsapp_call import WhatsAppCall
from app.routes.privacy import purge_meta_user_data
from app.services import messaging_policy
from app.services.lead_merge import merge_leads
from app.services.meta_token_service import encrypt_token
from tests.test_attribution_flow import _post

SDP_OFFER = "v=0\r\no=- 1 2 IN IP4 127.0.0.1\r\ns=-\r\na=ice-pwd:SEGREDO_DO_OFFER\r\n"
SDP_ANSWER = "v=0\r\no=- 3 4 IN IP4 127.0.0.1\r\ns=-\r\na=ice-pwd:SEGREDO_DA_ANSWER\r\n"


@pytest.fixture(autouse=True)
def _calling_on(monkeypatch):
    monkeypatch.setattr(settings, "whatsapp_calling_enabled", True)


@pytest.fixture
def ws():
    with patch.object(ws_manager, "send_to_users", new_callable=AsyncMock) as send, \
         patch.object(ws_manager, "is_online", new_callable=AsyncMock, return_value=False):
        yield send


def _user(tenant_id, db_session, *, role="agent", allowed=None, active=True):
    user = User(
        id=str(uuid.uuid4()), tenant_id=tenant_id, username=f"{uuid.uuid4().hex}@t.com",
        full_name=f"Agente {role}", password_hash="x", role=role, allowed_modules=allowed, is_active=active,
    )
    db_session.add(user)
    return user


def _headers(user):
    return {"Authorization": f"Bearer {create_access_token(user.id, user.tenant_id, user.role)}"}


async def _tenant(db_session):
    account = Account(brand_name="Calls")
    db_session.add(account)
    await db_session.flush()
    phone_number_id = uuid.uuid4().hex
    db_session.add(MetaConnection(
        id=str(uuid.uuid4()), account_id=account.id, provider=PROVIDER_WHATSAPP,
        phone_number_id=phone_number_id, waba_id="WABA_1",
        access_token_encrypted=encrypt_token("TOKEN_SECRETO"), status=STATUS_ACTIVE,
    ))
    admin = _user(account.id, db_session, role="admin")
    agent = _user(account.id, db_session, allowed=["whatsapp"])
    no_module = _user(account.id, db_session, allowed=["instagram"])
    await db_session.flush()
    return account, phone_number_id, admin, agent, no_module


def _event(phone_number_id, call_id, event="connect", *, frm="5583988887777", **extra):
    call = {
        "id": call_id, "from": frm, "from_user_id": "BR.13491208655302741918", "event": event,
        "timestamp": str(int(time.time())), "direction": "USER_INITIATED", **extra,
    }
    if frm is None:
        call.pop("from")
    if event == "connect":
        call.setdefault("session", {"sdp_type": "offer", "sdp": SDP_OFFER})
    contact = {"profile": {"name": "Maria"}, "user_id": "BR.13491208655302741918"}
    if frm:
        contact["wa_id"] = frm
    return {"object": "whatsapp_business_account", "entry": [{"id": "WABA_1", "changes": [{
        "field": "calls",
        "value": {
            "messaging_product": "whatsapp",
            "metadata": {"display_phone_number": "+55 83 3333-3333", "phone_number_id": phone_number_id},
            "contacts": [contact],
            "calls": [call],
        },
    }]}]}


async def _call(db_session, tenant_id, wa_call_id="wacid.1") -> WhatsAppCall:
    return (await db_session.execute(
        select(WhatsAppCall)
        .where(WhatsAppCall.tenant_id == tenant_id, WhatsAppCall.wa_call_id == wa_call_id)
        .execution_options(populate_existing=True)
    )).scalar_one()


async def _ringing(client, db_session, ws, phone_number_id, tenant_id, wa_call_id="wacid.1") -> WhatsAppCall:
    resp = await _post(client, _event(phone_number_id, wa_call_id))
    assert resp.status_code == 200
    return await _call(db_session, tenant_id, wa_call_id)


def _sent(ws, event_type):
    return [c.args for c in ws.call_args_list if c.args[2] == event_type]


class _FakeMeta:
    """Responde as chamadas à Graph API e guarda o que foi enviado."""

    def __init__(self, response=None, status=200):
        self.requests = []
        self.response = response or {"messaging_product": "whatsapp", "success": True}
        self.status = status

    def __enter__(self):
        real_client = httpx.AsyncClient

        def handler(request):
            self.requests.append(request)
            return httpx.Response(self.status, json=self.response)

        self._patch = patch(
            "app.services.whatsapp_service.httpx.AsyncClient",
            lambda **kw: real_client(transport=httpx.MockTransport(handler), **kw),
        )
        self._patch.start()
        return self

    def __exit__(self, *exc):
        self._patch.stop()

    @property
    def bodies(self):
        return [json.loads(r.content) for r in self.requests]


# ---------------------------------------------------------------------------
# Webhook
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_connect_records_history_and_rings_only_agents_with_module(client, db_session, ws):
    account, number, admin, agent, no_module = await _tenant(db_session)

    call = await _ringing(client, db_session, ws, number, account.id)

    assert call.status == "ringing" and call.direction == "inbound"
    assert call.contact_name == "Maria" and call.contact_wa_id == "5583988887777"
    rung = {args[1][0] for args in _sent(ws, "call_incoming")}
    assert rung == {admin.id, agent.id}
    assert no_module.id not in {uid for c in ws.call_args_list for uid in c.args[1]}

    msg = await db_session.get(Message, call.message_db_id)
    assert (msg.media_type, msg.direction, msg.text) == ("call", "inbound", None)
    assert msg.payload["call"]["status"] == "ringing"
    conv = await db_session.get(Conversation, call.conversation_id)
    assert conv.channel == "whatsapp" and conv.customer_id == call.lead_id


@pytest.mark.asyncio
async def test_sdp_stays_encrypted_and_out_of_events_payload_and_logs(client, db_session, ws, caplog):
    account, number, *_ = await _tenant(db_session)

    with caplog.at_level(logging.DEBUG):
        call = await _ringing(client, db_session, ws, number, account.id)

    assert "SEGREDO_DO_OFFER" not in call.sdp_offer_encrypted
    assert "SEGREDO_DO_OFFER" not in caplog.text
    assert "SEGREDO_DO_OFFER" not in json.dumps([c.args[3] for c in ws.call_args_list], default=str)
    msg = await db_session.get(Message, call.message_db_id)
    assert "SEGREDO_DO_OFFER" not in json.dumps(msg.payload)


@pytest.mark.asyncio
async def test_duplicate_connect_does_not_ring_twice(client, db_session, ws):
    account, number, *_ = await _tenant(db_session)

    await _ringing(client, db_session, ws, number, account.id)
    rings = len(_sent(ws, "call_incoming"))
    await _post(client, _event(number, "wacid.1"))

    assert len(_sent(ws, "call_incoming")) == rings
    rows = (await db_session.execute(select(WhatsAppCall).where(WhatsAppCall.tenant_id == account.id))).scalars().all()
    assert len(rows) == 1


@pytest.mark.asyncio
async def test_terminate_before_connect_never_rings(client, db_session, ws):
    account, number, *_ = await _tenant(db_session)

    await _post(client, _event(number, "wacid.1", "terminate", status="COMPLETED"))
    await _post(client, _event(number, "wacid.1"))

    call = await _call(db_session, account.id)
    assert call.status == "missed" and call.sdp_offer_encrypted is None
    assert _sent(ws, "call_incoming") == []


@pytest.mark.asyncio
async def test_late_connect_is_missed_without_ringing(client, db_session, ws):
    account, number, *_ = await _tenant(db_session)
    old = str(int(time.time()) - settings.whatsapp_call_ring_seconds - 5)

    await _post(client, _event(number, "wacid.1", timestamp=old))

    call = await _call(db_session, account.id)
    assert call.status == "missed" and call.sdp_offer_encrypted is None
    assert _sent(ws, "call_incoming") == []


@pytest.mark.asyncio
async def test_terminate_with_duration_completes_the_call(client, db_session, ws):
    account, number, *_ = await _tenant(db_session)
    call = await _ringing(client, db_session, ws, number, account.id)
    start = int(time.time())

    await _post(client, _event(
        number, "wacid.1", "terminate", status="COMPLETED",
        start_time=str(start), end_time=str(start + 95), duration=95,
    ))

    call = await _call(db_session, account.id)
    assert (call.status, call.duration_seconds) == ("completed", 95)
    assert call.sdp_offer_encrypted is None
    msg = await db_session.get(Message, call.message_db_id)
    assert msg.payload["call"]["duration_seconds"] == 95
    conv = await db_session.get(Conversation, call.conversation_id)
    assert conv.unread_count == 0


@pytest.mark.asyncio
async def test_unanswered_call_is_missed_and_counts_unread_once(client, db_session, ws):
    account, number, *_ = await _tenant(db_session)
    await _ringing(client, db_session, ws, number, account.id)

    for _ in range(2):
        await _post(client, _event(number, "wacid.1", "terminate", status="COMPLETED"))

    call = await _call(db_session, account.id)
    assert call.status == "missed"
    conv = await db_session.get(Conversation, call.conversation_id)
    assert conv.unread_count == 1


@pytest.mark.asyncio
async def test_failed_call_keeps_the_error_code(client, db_session, ws):
    account, number, *_ = await _tenant(db_session)
    await _ringing(client, db_session, ws, number, account.id)

    await _post(client, _event(
        number, "wacid.1", "terminate", status="FAILED",
        errors=[{"code": 138021, "message": "Media receive timeout"}],
    ))

    call = await _call(db_session, account.id)
    assert (call.status, call.error_code) == ("failed", 138021)


@pytest.mark.asyncio
async def test_flag_off_ignores_webhook_and_hides_routes(client, db_session, ws, monkeypatch):
    account, number, admin, *_ = await _tenant(db_session)
    monkeypatch.setattr(settings, "whatsapp_calling_enabled", False)

    resp = await _post(client, _event(number, "wacid.1"))
    assert resp.status_code == 200
    rows = (await db_session.execute(select(WhatsAppCall).where(WhatsAppCall.tenant_id == account.id))).scalars().all()
    assert rows == [] and ws.call_args_list == []

    assert (await client.get("/api/v1/whatsapp/calls/active", headers=_headers(admin))).status_code == 404
    assert (await client.get("/api/v1/auth/me", headers=_headers(admin))).json()["calling_enabled"] is False


@pytest.mark.asyncio
async def test_calls_field_does_not_reach_the_message_handler(client, db_session, ws):
    _, number, *_ = await _tenant(db_session)

    with patch("app.routes.webhook.handle_whatsapp_message", new_callable=AsyncMock) as handler:
        await _post(client, _event(number, "wacid.1"))

    handler.assert_not_called()


@pytest.mark.asyncio
async def test_number_connected_to_two_tenants_rings_nobody(client, db_session, ws):
    account, number, *_ = await _tenant(db_session)
    other = Account(brand_name="Outro")
    db_session.add(other)
    await db_session.flush()
    db_session.add(MetaConnection(
        id=str(uuid.uuid4()), account_id=other.id, provider=PROVIDER_WHATSAPP, phone_number_id=number,
        access_token_encrypted=encrypt_token("x"), status=STATUS_ACTIVE,
    ))
    await db_session.flush()

    resp = await _post(client, _event(number, "wacid.1"))

    assert resp.status_code == 200
    assert ws.call_args_list == []


@pytest.mark.asyncio
async def test_inbound_call_reopens_the_24h_window(client, db_session, ws):
    account, number, *_ = await _tenant(db_session)
    call = await _ringing(client, db_session, ws, number, account.id)

    assert await messaging_policy.is_within_window(db_session, account.id, conv_id=call.conversation_id)


@pytest.mark.asyncio
async def test_contact_without_phone_is_identified_by_bsuid(client, db_session, ws):
    account, number, *_ = await _tenant(db_session)

    await _post(client, _event(number, "wacid.1", frm=None))

    call = await _call(db_session, account.id)
    lead = await db_session.get(Lead, call.lead_id)
    assert lead.instagram_handle == "BR.13491208655302741918" and lead.phone is None
    assert call.contact_wa_id == "BR.13491208655302741918"


@pytest.mark.asyncio
async def test_assigned_agent_rings_first_and_others_wait(client, db_session, ws):
    account, number, admin, agent, _ = await _tenant(db_session)
    await _ringing(client, db_session, ws, number, account.id)
    call = await _call(db_session, account.id)
    conv = await db_session.get(Conversation, call.conversation_id)
    conv.atendente_id = agent.id
    await db_session.commit()
    ws.reset_mock()

    with patch.object(ws_manager, "is_online", new_callable=AsyncMock, return_value=True):
        await _post(client, _event(number, "wacid.2"))
    delays = {args[1][0]: args[3]["ring_after_ms"] for args in _sent(ws, "call_incoming")}
    assert delays[agent.id] == 0
    assert 0 < delays[admin.id] <= settings.whatsapp_call_escalation_seconds * 1000

    # Atendente offline: ninguém espera.
    ws.reset_mock()
    await _post(client, _event(number, "wacid.3"))
    delays = {args[1][0]: args[3]["ring_after_ms"] for args in _sent(ws, "call_incoming")}
    assert set(delays.values()) == {0}


# ---------------------------------------------------------------------------
# Atender
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_first_agent_to_claim_wins(client, db_session, ws):
    account, number, admin, agent, _ = await _tenant(db_session)
    call = await _ringing(client, db_session, ws, number, account.id)

    first = await client.post(f"/api/v1/whatsapp/calls/{call.id}/claim", headers=_headers(agent))
    second = await client.post(f"/api/v1/whatsapp/calls/{call.id}/claim", headers=_headers(admin))

    assert first.status_code == 200 and first.json()["sdp_offer"] == SDP_OFFER
    assert second.status_code == 409 and second.json()["detail"]["code"] == "call_unavailable"

    call = await _call(db_session, account.id)
    assert (call.status, call.answered_by_user_id) == ("claimed", agent.id)
    assert call.answered_by_name == agent.full_name
    assert call.sdp_offer_encrypted is None
    conv = await db_session.get(Conversation, call.conversation_id)
    assert (conv.atendente_id, conv.bot_active, conv.atendimento_status) == (agent.id, False, "em_atendimento")


@pytest.mark.asyncio
async def test_claim_expired_call_is_refused(client, db_session, ws):
    account, number, _, agent, _ = await _tenant(db_session)
    call = await _ringing(client, db_session, ws, number, account.id)
    call.ring_expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)
    await db_session.commit()

    resp = await client.post(f"/api/v1/whatsapp/calls/{call.id}/claim", headers=_headers(agent))

    assert resp.status_code == 409


@pytest.mark.asyncio
async def test_other_tenant_and_agent_without_module_cannot_touch_the_call(client, db_session, ws):
    account, number, _, _, no_module = await _tenant(db_session)
    call = await _ringing(client, db_session, ws, number, account.id)
    _, _, other_admin, _, _ = await _tenant(db_session)

    for action in ("claim", "reject", "terminate"):
        resp = await client.post(f"/api/v1/whatsapp/calls/{call.id}/{action}", headers=_headers(other_admin))
        assert resp.status_code == 404, action
    assert (await client.get("/api/v1/whatsapp/calls/active", headers=_headers(other_admin))).json() == []

    resp = await client.post(f"/api/v1/whatsapp/calls/{call.id}/claim", headers=_headers(no_module))
    assert resp.status_code == 403
    assert (await _call(db_session, account.id)).status == "ringing"


@pytest.mark.asyncio
async def test_active_calls_lists_only_calls_still_ringing(client, db_session, ws):
    account, number, _, agent, _ = await _tenant(db_session)
    call = await _ringing(client, db_session, ws, number, account.id)

    active = (await client.get("/api/v1/whatsapp/calls/active", headers=_headers(agent))).json()
    assert [c["id"] for c in active] == [call.id]
    assert "sdp" not in json.dumps(active).lower()

    await client.post(f"/api/v1/whatsapp/calls/{call.id}/claim", headers=_headers(agent))
    assert (await client.get("/api/v1/whatsapp/calls/active", headers=_headers(agent))).json() == []


@pytest.mark.asyncio
async def test_pre_accept_and_accept_send_the_sdp_answer_to_meta(client, db_session, ws):
    account, number, _, agent, _ = await _tenant(db_session)
    call = await _ringing(client, db_session, ws, number, account.id)
    await client.post(f"/api/v1/whatsapp/calls/{call.id}/claim", headers=_headers(agent))

    with _FakeMeta() as meta:
        pre = await client.post(f"/api/v1/whatsapp/calls/{call.id}/pre-accept", json={"sdp": SDP_ANSWER}, headers=_headers(agent))
        acc = await client.post(f"/api/v1/whatsapp/calls/{call.id}/accept", json={"sdp": SDP_ANSWER}, headers=_headers(agent))

    assert pre.status_code == 200 and acc.status_code == 200
    assert meta.requests[0].url.path.endswith(f"/{number}/calls")
    assert meta.requests[0].headers["authorization"] == "Bearer TOKEN_SECRETO"
    assert [b["action"] for b in meta.bodies] == ["pre_accept", "accept"]
    for body in meta.bodies:
        assert body["call_id"] == "wacid.1" and body["messaging_product"] == "whatsapp"
        assert body["session"] == {"sdp_type": "answer", "sdp": SDP_ANSWER}

    call = await _call(db_session, account.id)
    assert call.status == "connected" and call.started_at is not None


@pytest.mark.asyncio
async def test_only_the_agent_who_claimed_can_accept(client, db_session, ws):
    account, number, admin, agent, _ = await _tenant(db_session)
    call = await _ringing(client, db_session, ws, number, account.id)
    await client.post(f"/api/v1/whatsapp/calls/{call.id}/claim", headers=_headers(agent))

    with _FakeMeta() as meta:
        resp = await client.post(f"/api/v1/whatsapp/calls/{call.id}/accept", json={"sdp": SDP_ANSWER}, headers=_headers(admin))

    assert resp.status_code == 403
    assert meta.requests == []


@pytest.mark.asyncio
async def test_meta_error_is_explained_and_not_retried_or_logged(client, db_session, ws, caplog):
    account, number, _, agent, _ = await _tenant(db_session)
    call = await _ringing(client, db_session, ws, number, account.id)
    await client.post(f"/api/v1/whatsapp/calls/{call.id}/claim", headers=_headers(agent))

    refusal = {"error": {"code": 138000, "message": f"Calling not enabled {SDP_ANSWER}"}}
    with _FakeMeta(refusal, status=500) as meta, caplog.at_level(logging.INFO):
        resp = await client.post(f"/api/v1/whatsapp/calls/{call.id}/accept", json={"sdp": SDP_ANSWER}, headers=_headers(agent))

    assert len(meta.requests) == 1
    assert resp.status_code == 502
    assert resp.json()["detail"]["meta_code"] == 138000
    assert "SEGREDO_DA_ANSWER" not in caplog.text and "TOKEN_SECRETO" not in caplog.text
    assert (await _call(db_session, account.id)).status == "claimed"


@pytest.mark.asyncio
async def test_reject_ends_the_call_for_everyone(client, db_session, ws):
    account, number, admin, agent, _ = await _tenant(db_session)
    call = await _ringing(client, db_session, ws, number, account.id)

    with _FakeMeta() as meta:
        resp = await client.post(f"/api/v1/whatsapp/calls/{call.id}/reject", headers=_headers(agent))

    assert resp.status_code == 200
    assert meta.bodies[0]["action"] == "reject" and "session" not in meta.bodies[0]
    call = await _call(db_session, account.id)
    assert (call.status, call.rejected_by_name) == ("rejected", agent.full_name)
    assert call.sdp_offer_encrypted is None
    assert (await client.post(f"/api/v1/whatsapp/calls/{call.id}/claim", headers=_headers(admin))).status_code == 409

    # O terminate da Meta depois do reject não transforma em chamada perdida.
    await _post(client, _event(number, "wacid.1", "terminate", status="COMPLETED"))
    assert (await _call(db_session, account.id)).status == "rejected"


@pytest.mark.asyncio
async def test_reject_after_someone_claimed_does_not_drop_the_call(client, db_session, ws):
    account, number, admin, agent, _ = await _tenant(db_session)
    call = await _ringing(client, db_session, ws, number, account.id)
    await client.post(f"/api/v1/whatsapp/calls/{call.id}/claim", headers=_headers(agent))

    with _FakeMeta() as meta:
        resp = await client.post(f"/api/v1/whatsapp/calls/{call.id}/reject", headers=_headers(admin))

    assert resp.status_code == 409
    assert meta.requests == []


@pytest.mark.asyncio
async def test_failed_reject_keeps_the_call_ringing(client, db_session, ws):
    account, number, _, agent, _ = await _tenant(db_session)
    call = await _ringing(client, db_session, ws, number, account.id)

    with _FakeMeta({"error": {"code": 1, "message": "x"}}, status=400):
        resp = await client.post(f"/api/v1/whatsapp/calls/{call.id}/reject", headers=_headers(agent))

    assert resp.status_code == 502
    assert (await _call(db_session, account.id)).status == "ringing"


@pytest.mark.asyncio
async def test_terminate_uses_the_right_action_and_webhook_sets_final_duration(client, db_session, ws):
    account, number, admin, agent, no_module = await _tenant(db_session)
    call = await _ringing(client, db_session, ws, number, account.id)
    await client.post(f"/api/v1/whatsapp/calls/{call.id}/claim", headers=_headers(agent))

    other = _user(account.id, db_session, allowed=["whatsapp"])
    await db_session.flush()
    assert (await client.post(f"/api/v1/whatsapp/calls/{call.id}/terminate", headers=_headers(other))).status_code == 403

    with _FakeMeta() as meta:
        await client.post(f"/api/v1/whatsapp/calls/{call.id}/accept", json={"sdp": SDP_ANSWER}, headers=_headers(agent))
        resp = await client.post(f"/api/v1/whatsapp/calls/{call.id}/terminate", headers=_headers(agent))
    assert resp.status_code == 200 and meta.bodies[-1]["action"] == "terminate"
    assert (await _call(db_session, account.id)).status == "completed"

    await _post(client, _event(number, "wacid.1", "terminate", status="COMPLETED", duration=42))
    call = await _call(db_session, account.id)
    assert (call.status, call.duration_seconds) == ("completed", 42)


@pytest.mark.asyncio
async def test_terminate_before_accept_uses_reject_and_counts_as_missed(client, db_session, ws):
    account, number, _, agent, _ = await _tenant(db_session)
    call = await _ringing(client, db_session, ws, number, account.id)
    await client.post(f"/api/v1/whatsapp/calls/{call.id}/claim", headers=_headers(agent))

    with _FakeMeta() as meta:
        resp = await client.post(f"/api/v1/whatsapp/calls/{call.id}/terminate", headers=_headers(agent))

    assert resp.status_code == 200 and meta.bodies[0]["action"] == "reject"
    assert (await _call(db_session, account.id)).status == "missed"


# ---------------------------------------------------------------------------
# Configurações do número
# ---------------------------------------------------------------------------

HOURS = {
    "status": "ENABLED", "timezone_id": "America/Sao_Paulo",
    "weekly_operating_hours": [{"day_of_week": "MONDAY", "open_time": "0900", "close_time": "1800"}],
}


@pytest.mark.asyncio
async def test_settings_show_status_limit_and_restrictions(client, db_session):
    _, _, admin, _, _ = await _tenant(db_session)
    response = {
        "calling": {"status": "ENABLED"},
        "restrictions": {"restrictions_list": [{"type": "RESTRICTED_USER_INITIATED_CALLING", "expiration": 1}]},
        "whatsapp_business_manager_messaging_limit": "TIER_250",
    }
    with _FakeMeta(response):
        resp = await client.get("/api/v1/whatsapp/calling/settings", headers=_headers(admin))

    body = resp.json()
    assert body["connected"] and body["enabled"]
    assert (body["messaging_limit"], body["meets_messaging_limit"]) == ("TIER_250", False)
    assert body["restrictions"][0]["type"] == "RESTRICTED_USER_INITIATED_CALLING"


@pytest.mark.asyncio
async def test_settings_without_connection_is_not_an_error(client, make_user):
    _, headers = await make_user()
    resp = await client.get("/api/v1/whatsapp/calling/settings", headers=headers)
    assert resp.status_code == 200 and resp.json()["connected"] is False


@pytest.mark.asyncio
async def test_only_admin_changes_settings_and_holidays_are_kept(client, db_session):
    _, number, admin, agent, _ = await _tenant(db_session)
    body = {"enabled": True, "call_hours": HOURS}

    assert (await client.put("/api/v1/whatsapp/calling/settings", json=body, headers=_headers(agent))).status_code == 403

    holidays = [{"date": "2026-12-25", "start_time": "0000", "end_time": "2359"}]
    response = {"success": True, "calling": {"status": "ENABLED", "call_hours": {"holiday_schedule": holidays}}}
    with _FakeMeta(response) as meta:
        resp = await client.put("/api/v1/whatsapp/calling/settings", json=body, headers=_headers(admin))

    assert resp.status_code == 200 and resp.json()["enabled"]
    update = next(r for r in meta.requests if r.method == "POST")
    assert update.url.path.endswith(f"/{number}/settings")
    calling = json.loads(update.content)["calling"]
    assert calling["status"] == "ENABLED"
    assert calling["call_hours"]["weekly_operating_hours"] == HOURS["weekly_operating_hours"]
    assert calling["call_hours"]["holiday_schedule"] == holidays


@pytest.mark.asyncio
async def test_enabling_below_the_limit_explains_the_reason(client, db_session):
    _, _, admin, _, _ = await _tenant(db_session)
    refusal = {"error": {"code": 138015, "message": "Calling cannot be enabled"}}

    with _FakeMeta(refusal, status=400):
        resp = await client.put("/api/v1/whatsapp/calling/settings", json={"enabled": True}, headers=_headers(admin))

    assert resp.status_code == 502
    assert resp.json()["detail"]["meta_code"] == 138015
    assert "2.000" in resp.json()["detail"]["message"] or "2,000" in resp.json()["detail"]["message"]


@pytest.mark.parametrize("hours", [
    {**HOURS, "weekly_operating_hours": []},
    {**HOURS, "weekly_operating_hours": [{"day_of_week": "MONDAY", "open_time": "1800", "close_time": "0900"}]},
    {**HOURS, "weekly_operating_hours": [{"day_of_week": "SEGUNDA", "open_time": "0900", "close_time": "1800"}]},
    {**HOURS, "weekly_operating_hours": [{"day_of_week": "MONDAY", "open_time": "9h", "close_time": "1800"}]},
])
@pytest.mark.asyncio
async def test_invalid_call_hours_never_reach_meta(client, db_session, hours):
    _, _, admin, _, _ = await _tenant(db_session)

    with _FakeMeta() as meta:
        resp = await client.put("/api/v1/whatsapp/calling/settings", json={"enabled": True, "call_hours": hours}, headers=_headers(admin))

    assert resp.status_code == 422
    assert meta.requests == []


# ---------------------------------------------------------------------------
# Histórico do lead
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_lead_history_shows_who_answered_and_is_isolated(client, db_session, ws):
    account, number, _, agent, _ = await _tenant(db_session)
    call = await _ringing(client, db_session, ws, number, account.id)
    await client.post(f"/api/v1/whatsapp/calls/{call.id}/claim", headers=_headers(agent))
    await _post(client, _event(number, "wacid.1", "terminate", status="COMPLETED", duration=30))

    rows = (await client.get(f"/api/v1/whatsapp/leads/{call.lead_id}/calls", headers=_headers(agent))).json()
    assert len(rows) == 1
    assert rows[0]["direction"] == "inbound" and rows[0]["status"] == "completed"
    assert rows[0]["duration_seconds"] == 30 and rows[0]["answered_by"] == agent.full_name

    _, _, other_admin, _, _ = await _tenant(db_session)
    resp = await client.get(f"/api/v1/whatsapp/leads/{call.lead_id}/calls", headers=_headers(other_admin))
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_lost_terminate_shows_as_missed_after_the_window(client, db_session, ws):
    account, number, _, agent, _ = await _tenant(db_session)
    call = await _ringing(client, db_session, ws, number, account.id)
    call.ring_expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)
    await db_session.commit()

    rows = (await client.get(f"/api/v1/whatsapp/leads/{call.lead_id}/calls", headers=_headers(agent))).json()

    assert rows[0]["status"] == "missed"


@pytest.mark.asyncio
async def test_merging_leads_keeps_the_call_history(client, db_session, ws):
    account, number, *_ = await _tenant(db_session)
    call = await _ringing(client, db_session, ws, number, account.id)
    absorbed = await db_session.get(Lead, call.lead_id)
    survivor = Lead(id=str(uuid.uuid4()), account_id=account.id, instagram_handle=uuid.uuid4().hex, source=absorbed.source)
    db_session.add(survivor)
    await db_session.flush()

    await merge_leads(survivor, absorbed, db_session)

    assert (await _call(db_session, account.id)).lead_id == survivor.id


@pytest.mark.asyncio
async def test_data_deletion_removes_calls(client, db_session, ws):
    account, number, *_ = await _tenant(db_session)
    await _ringing(client, db_session, ws, number, account.id)
    meta_user_id = uuid.uuid4().hex
    conn = (await db_session.execute(
        select(MetaConnection).where(MetaConnection.account_id == account.id)
    )).scalar_one()
    conn.meta_user_id = meta_user_id
    call = await _call(db_session, account.id)
    lead = await db_session.get(Lead, call.lead_id)
    lead.instagram_handle = meta_user_id
    await db_session.flush()

    await purge_meta_user_data(db_session, meta_user_id)

    rows = (await db_session.execute(select(WhatsAppCall).where(WhatsAppCall.tenant_id == account.id))).scalars().all()
    assert rows == []


# ---------------------------------------------------------------------------
# Quem acessa o módulo
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_users_with_module_respects_user_list_blocked_account_and_inactive(db_session):
    account, _, admin, agent, no_module = await _tenant(db_session)
    inactive = _user(account.id, db_session, allowed=["whatsapp"], active=False)
    await db_session.flush()

    ids = await users_with_module(db_session, account.id, "whatsapp")
    assert set(ids) == {admin.id, agent.id}
    assert no_module.id not in ids and inactive.id not in ids

    account.blocked_modules = ["whatsapp"]
    await db_session.flush()
    assert await users_with_module(db_session, account.id, "whatsapp") == []


# ---------------------------------------------------------------------------
# WebSocket
# ---------------------------------------------------------------------------

class _Socket:
    def __init__(self):
        self.sent = []

    async def send_text(self, message):
        self.sent.append(json.loads(message))


@pytest.mark.asyncio
async def test_send_to_users_reaches_only_those_users_in_the_tenant():
    manager = ConnectionManager()
    mine, other, other_tenant, anonymous = _Socket(), _Socket(), _Socket(), _Socket()
    await manager.connect("t1", mine, "u1")
    await manager.connect("t1", other, "u2")
    await manager.connect("t2", other_tenant, "u1")
    await manager.connect("t1", anonymous)

    await manager.send_to_users("t1", ["u1"], "call_incoming", {"id": "c"})
    await manager.broadcast("t1", "new_message", {"id": 1})

    assert [m["event"] for m in mine.sent] == ["call_incoming", "new_message"]
    assert [m["event"] for m in other.sent] == ["new_message"]
    assert [m["event"] for m in anonymous.sent] == ["new_message"]
    assert other_tenant.sent == []

    await manager.disconnect("t1", mine)
    await manager.send_to_users("t1", ["u1"], "call_updated", {})
    assert len(mine.sent) == 2


class _FakeRedis:
    def __init__(self):
        self.published = []

    async def publish(self, channel, message):
        self.published.append(message)


@pytest.mark.asyncio
async def test_fanout_delivers_to_other_instances_and_not_back_to_itself(monkeypatch):
    monkeypatch.setattr(settings, "ws_redis_fanout", True)
    redis = _FakeRedis()
    first, second = ConnectionManager(), ConnectionManager()
    on_first, on_second, not_target = _Socket(), _Socket(), _Socket()
    await first.connect("t1", on_first, "u1")
    await second.connect("t1", on_second, "u1")
    await second.connect("t1", not_target, "u2")

    with patch("app.core.ws_manager.get_redis_client", new_callable=AsyncMock, return_value=redis):
        await first.send_to_users("t1", ["u1"], "call_incoming", {"id": "c"})

    await first._on_fanout(redis.published[0])
    await second._on_fanout(redis.published[0])

    assert len(on_first.sent) == 1  # entrega local, sem repetir pelo Redis
    assert on_second.sent == on_first.sent
    assert not_target.sent == []


@pytest.mark.asyncio
async def test_fanout_failure_does_not_stop_local_delivery(monkeypatch):
    monkeypatch.setattr(settings, "ws_redis_fanout", True)
    manager = ConnectionManager()
    socket = _Socket()
    await manager.connect("t1", socket, "u1")

    with patch("app.core.ws_manager.get_redis_client", new_callable=AsyncMock, side_effect=OSError("down")):
        await manager.broadcast("t1", "new_message", {"id": 1})

    assert len(socket.sent) == 1


@pytest.mark.asyncio
async def test_fanout_off_does_not_touch_redis():
    manager = ConnectionManager()
    with patch("app.core.ws_manager.get_redis_client", new_callable=AsyncMock) as get_client:
        await manager.broadcast("t1", "new_message", {"id": 1})
    get_client.assert_not_called()


def test_jwt_in_websocket_url_is_redacted_from_logs():
    record = logging.LogRecord(
        "uvicorn.error", logging.INFO, __file__, 1, '%s - "WebSocket %s" [accepted]',
        ("1.2.3.4:5", "/ws?token=eyJhbGciOi.SEGREDO.assinatura"), None,
    )

    assert _RedactSecretsFilter().filter(record)

    assert "SEGREDO" not in record.getMessage()
    assert "/ws?token=***" in record.getMessage()
    assert "uvicorn.error" in [
        name for name in ("httpx", "uvicorn.error")
        if any(isinstance(f, _RedactSecretsFilter) for f in logging.getLogger(name).filters)
    ]


# ---------------------------------------------------------------------------
# Webhook de mensagens: contato sem wa_id (nome de usuário)
# ---------------------------------------------------------------------------

def _message_payload(phone_number_id, **message):
    return {"object": "whatsapp_business_account", "entry": [{"id": "WABA_1", "changes": [{
        "field": "messages",
        "value": {
            "messaging_product": "whatsapp",
            "metadata": {"phone_number_id": phone_number_id},
            "contacts": [{"profile": {"name": "Sem Telefone"}, "user_id": "BR.999"}],
            "messages": [{
                "id": f"wamid.{uuid.uuid4().hex}", "from_user_id": "BR.999",
                "timestamp": str(int(time.time())), **message,
            }],
        },
    }]}]}


@pytest.mark.asyncio
async def test_message_without_wa_id_does_not_crash_and_has_no_fake_phone(client, db_session):
    account, number, *_ = await _tenant(db_session)

    resp = await _post(client, _message_payload(number, type="text", text={"body": "oi"}))

    assert resp.status_code == 200
    lead = (await db_session.execute(select(Lead).where(Lead.account_id == account.id))).scalar_one()
    assert lead.instagram_handle == "BR.999" and lead.phone is None and lead.name == "Sem Telefone"
    msg = (await db_session.execute(select(Message).where(Message.tenant_id == account.id))).scalar_one()
    assert msg.text == "oi"


@pytest.mark.asyncio
async def test_call_permission_reply_is_not_saved_as_a_customer_message(client, db_session):
    account, number, *_ = await _tenant(db_session)

    resp = await _post(client, _message_payload(number, type="interactive", interactive={
        "type": "call_permission_reply",
        "call_permission_reply": {"response": "accept", "is_permanent": True, "response_source": "user_action"},
    }))

    assert resp.status_code == 200
    rows = (await db_session.execute(select(Message).where(Message.tenant_id == account.id))).scalars().all()
    assert rows == []
