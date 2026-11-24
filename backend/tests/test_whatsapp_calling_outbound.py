"""
Ligação feita pela empresa (Calling API, BUSINESS_INITIATED): consentimento no
Prospecta, permissão do cliente na Meta, sinalização pelo webhook e o que nunca vaza.
"""
import json
import logging
import time
import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy import select

from app.core.config import settings
from app.core.ws_manager import ws_manager
from app.models.conversation import Conversation
from app.models.lead import Lead, LeadSource, LeadStatus
from app.models.message import Message
from app.models.whatsapp_call import WhatsAppCall
from tests.test_attribution_flow import _post
from tests.test_whatsapp_calling import _FakeMeta, _headers, _tenant

SDP_OFFER = "v=0\r\no=- 1 2 IN IP4 127.0.0.1\r\ns=-\r\na=ice-pwd:SEGREDO_DO_NAVEGADOR\r\n"
SDP_ANSWER = "v=0\r\no=- 3 4 IN IP4 127.0.0.1\r\ns=-\r\na=ice-pwd:SEGREDO_DO_CLIENTE\r\n"
PHONE = "5583991112222"


@pytest.fixture(autouse=True)
def _calling_on(monkeypatch):
    monkeypatch.setattr(settings, "whatsapp_calling_enabled", True)


@pytest.fixture(autouse=True)
def ws():
    with patch.object(ws_manager, "send_to_users", new_callable=AsyncMock) as send, \
         patch.object(ws_manager, "broadcast", new_callable=AsyncMock), \
         patch.object(ws_manager, "is_online", new_callable=AsyncMock, return_value=False):
        yield send


async def _lead(db_session, tenant_id, *, opt_in=True, opted_out=False, phone=PHONE, window=False):
    lead = Lead(
        id=str(uuid.uuid4()), account_id=tenant_id, instagram_handle=phone or uuid.uuid4().hex, phone=phone,
        name="Joana", source=LeadSource.MANUAL, status=LeadStatus.NEW, whatsapp_opt_in=opt_in,
        whatsapp_opted_out_at=datetime.now(timezone.utc) if opted_out else None,
    )
    db_session.add(lead)
    await db_session.flush()
    if window:
        conv = Conversation(id=str(uuid.uuid4()), tenant_id=tenant_id, customer_id=lead.id, channel="whatsapp")
        db_session.add(conv)
        await db_session.flush()
        db_session.add(Message(tenant_id=tenant_id, conversation_id=conv.id, sender=phone, text="oi",
                               direction="inbound", wa_id=phone, status="delivered"))
        await db_session.flush()
    return lead


def _calls_event(phone_number_id, *, calls=None, statuses=None):
    value = {"messaging_product": "whatsapp", "metadata": {"phone_number_id": phone_number_id}}
    if calls:
        value["calls"] = calls
    if statuses:
        value["statuses"] = statuses
    return {"object": "whatsapp_business_account", "entry": [{"id": "WABA_1", "changes": [
        {"field": "calls", "value": value},
    ]}]}


def _bic(call_id, event, **extra):
    return {"id": call_id, "to": PHONE, "from": "558333333333", "event": event,
            "direction": "BUSINESS_INITIATED", "timestamp": str(int(time.time())), **extra}


async def _get_call(db_session, call_id) -> WhatsAppCall:
    return (await db_session.execute(
        select(WhatsAppCall).where(WhatsAppCall.id == call_id).execution_options(populate_existing=True)
    )).scalar_one()


async def _dial(client, db_session, agent, lead, wa_call_id="wacid.out1"):
    with _FakeMeta({"messaging_product": "whatsapp", "calls": [{"id": wa_call_id}], "success": True}) as meta:
        resp = await client.post("/api/v1/whatsapp/calls/outbound", headers=_headers(agent),
                                 json={"lead_id": lead.id, "sdp": SDP_OFFER})
    assert resp.status_code == 200, resp.text
    return await _get_call(db_session, resp.json()["id"]), meta


# ---------------------------------------------------------------------------
# Consentimento e permissão
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
@pytest.mark.parametrize("kwargs,reason", [
    ({"opt_in": False}, "no_opt_in"),
    ({"opted_out": True}, "opted_out"),
    ({"phone": None}, "no_phone"),
])
async def test_no_consent_blocks_without_asking_meta(client, db_session, kwargs, reason):
    account, _, _, agent, _ = await _tenant(db_session)
    lead = await _lead(db_session, account.id, **kwargs)

    with _FakeMeta() as meta:
        perm = await client.get(f"/api/v1/whatsapp/leads/{lead.id}/call-permission", headers=_headers(agent))
        call = await client.post("/api/v1/whatsapp/calls/outbound", headers=_headers(agent),
                                 json={"lead_id": lead.id, "sdp": SDP_OFFER})

    assert perm.json()["can_call"] is False and perm.json()["reason"] == reason
    assert call.status_code == 409 and call.json()["detail"]["code"] == reason
    assert meta.requests == []


@pytest.mark.asyncio
async def test_permission_reflects_meta(client, db_session):
    account, _, _, agent, _ = await _tenant(db_session)
    lead = await _lead(db_session, account.id)

    granted = {"permission": {"status": "temporary", "expiration_time": 1745343479},
               "actions": [{"action_name": "start_call", "can_perform_action": True}]}
    with _FakeMeta(granted) as meta:
        resp = await client.get(f"/api/v1/whatsapp/leads/{lead.id}/call-permission", headers=_headers(agent))
    assert resp.json()["can_call"] is True
    assert meta.requests[0].url.params["user_wa_id"] == PHONE

    none = {"permission": {"status": "no_permission"},
            "actions": [{"action_name": "send_call_permission_request", "can_perform_action": True}]}
    with _FakeMeta(none):
        resp = await client.get(f"/api/v1/whatsapp/leads/{lead.id}/call-permission", headers=_headers(agent))
    body = resp.json()
    assert body["can_call"] is False and body["can_request"] is True and body["reason"] == "no_permission"


@pytest.mark.asyncio
async def test_permission_request_needs_open_window(client, db_session):
    account, _, _, agent, _ = await _tenant(db_session)
    closed = await _lead(db_session, account.id)
    with _FakeMeta() as meta:
        resp = await client.post(f"/api/v1/whatsapp/leads/{closed.id}/call-permission-request",
                                 headers=_headers(agent), json={})
    assert resp.status_code == 422 and resp.json()["detail"]["code"] == "outside_24h_window"
    assert meta.requests == []

    open_ = await _lead(db_session, account.id, phone="5583997776666", window=True)
    with _FakeMeta({"messages": [{"id": "wamid.perm"}]}) as meta:
        resp = await client.post(f"/api/v1/whatsapp/leads/{open_.id}/call-permission-request",
                                 headers=_headers(agent), json={"text": "Posso te ligar?"})
    assert resp.status_code == 200
    sent = meta.bodies[0]
    assert sent["interactive"]["type"] == "call_permission_request"
    assert sent["interactive"]["body"]["text"] == "Posso te ligar?" and sent["to"] == "5583997776666"
    saved = (await db_session.execute(select(Message).where(Message.message_id == "wamid.perm"))).scalar_one()
    assert saved.direction == "outbound" and saved.payload == {"call_permission_request": True}


@pytest.mark.asyncio
async def test_permission_reply_goes_to_history_once(client, db_session):
    account, number, *_ = await _tenant(db_session)
    lead = await _lead(db_session, account.id, window=True)
    payload = {"object": "whatsapp_business_account", "entry": [{"id": "WABA_1", "changes": [{"field": "messages", "value": {
        "messaging_product": "whatsapp", "metadata": {"phone_number_id": number},
        "contacts": [{"profile": {"name": "Joana"}, "wa_id": PHONE}],
        "messages": [{"from": PHONE, "id": "wamid.reply1", "timestamp": str(int(time.time())), "type": "interactive",
                      "interactive": {"type": "call_permission_reply", "call_permission_reply": {
                          "response": "accept", "is_permanent": True, "response_source": "user_action"}}}],
    }}]}]}

    await _post(client, payload)
    await _post(client, payload)

    rows = (await db_session.execute(select(Message).where(Message.message_id == "wamid.reply1"))).scalars().all()
    assert len(rows) == 1
    assert rows[0].media_type == "call_permission" and rows[0].payload["call_permission"]["response"] == "accept"
    conv = await db_session.get(Conversation, rows[0].conversation_id)
    assert conv.customer_id == lead.id


# ---------------------------------------------------------------------------
# Ligar
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_dial_sends_offer_and_records_call_without_leaking_sdp(client, db_session, caplog):
    account, _, _, agent, _ = await _tenant(db_session)
    lead = await _lead(db_session, account.id)

    with caplog.at_level(logging.DEBUG):
        call, meta = await _dial(client, db_session, agent, lead)

    body = meta.bodies[0]
    assert body["action"] == "connect" and body["to"] == PHONE
    assert body["session"] == {"sdp_type": "offer", "sdp": SDP_OFFER}
    assert (call.direction, call.status, call.wa_call_id) == ("outbound", "dialing", "wacid.out1")
    assert call.answered_by_user_id == agent.id
    msg = await db_session.get(Message, call.message_db_id)
    assert (msg.media_type, msg.direction) == ("call", "outbound")
    assert "SEGREDO_DO_NAVEGADOR" not in caplog.text
    assert "SEGREDO_DO_NAVEGADOR" not in json.dumps(msg.payload)


@pytest.mark.asyncio
async def test_meta_refusal_marks_call_failed_with_friendly_message(client, db_session):
    account, _, _, agent, _ = await _tenant(db_session)
    lead = await _lead(db_session, account.id)

    with _FakeMeta({"error": {"code": 138006, "message": "no permission"}}, status=400):
        resp = await client.post("/api/v1/whatsapp/calls/outbound", headers=_headers(agent),
                                 json={"lead_id": lead.id, "sdp": SDP_OFFER})

    assert resp.status_code == 502
    assert "permit" in resp.json()["detail"]["message"].lower()
    call = (await db_session.execute(select(WhatsAppCall).where(WhatsAppCall.lead_id == lead.id))).scalar_one()
    assert call.status == "failed" and call.error_code == 138006


@pytest.mark.asyncio
async def test_one_call_at_a_time_per_agent(client, db_session):
    account, _, _, agent, _ = await _tenant(db_session)
    lead = await _lead(db_session, account.id)
    await _dial(client, db_session, agent, lead)

    with _FakeMeta() as meta:
        resp = await client.post("/api/v1/whatsapp/calls/outbound", headers=_headers(agent),
                                 json={"lead_id": lead.id, "sdp": SDP_OFFER})
    assert resp.status_code == 409 and resp.json()["detail"]["code"] == "already_in_call"
    assert meta.requests == []


@pytest.mark.asyncio
async def test_answer_sdp_reaches_only_the_caller_once(client, db_session, ws):
    account, number, admin, agent, _ = await _tenant(db_session)
    lead = await _lead(db_session, account.id)
    call, _ = await _dial(client, db_session, agent, lead)

    await _post(client, _calls_event(number, calls=[_bic("wacid.out1", "connect",
                                                         session={"sdp_type": "answer", "sdp": SDP_ANSWER})]))

    stored = await _get_call(db_session, call.id)
    assert stored.sdp_offer_encrypted and "SEGREDO_DO_CLIENTE" not in stored.sdp_offer_encrypted
    assert "SEGREDO_DO_CLIENTE" not in json.dumps([c.args for c in ws.call_args_list], default=str)

    other = await client.get(f"/api/v1/whatsapp/calls/{call.id}/remote-sdp", headers=_headers(admin))
    assert other.status_code == 403
    first = await client.get(f"/api/v1/whatsapp/calls/{call.id}/remote-sdp", headers=_headers(agent))
    assert first.json()["sdp"] == SDP_ANSWER
    again = await client.get(f"/api/v1/whatsapp/calls/{call.id}/remote-sdp", headers=_headers(agent))
    assert again.json()["sdp"] is None


@pytest.mark.asyncio
async def test_accepted_then_terminated_is_completed(client, db_session):
    account, number, _, agent, _ = await _tenant(db_session)
    lead = await _lead(db_session, account.id)
    call, _ = await _dial(client, db_session, agent, lead)

    status = {"id": "wacid.out1", "type": "call", "status": "ACCEPTED", "timestamp": str(int(time.time())),
              "recipient_id": PHONE}
    await _post(client, _calls_event(number, statuses=[status]))
    assert (await _get_call(db_session, call.id)).status == "connected"

    await _post(client, _calls_event(number, calls=[_bic("wacid.out1", "terminate", status="COMPLETED",
                                                         duration=42, start_time=str(int(time.time()) - 42))]))
    done = await _get_call(db_session, call.id)
    assert done.status == "completed" and done.duration_seconds == 42
    msg = await db_session.get(Message, done.message_db_id)
    assert msg.payload["call"]["status"] == "completed"


@pytest.mark.asyncio
async def test_rejected_and_unanswered(client, db_session):
    account, number, _, agent, _ = await _tenant(db_session)
    lead = await _lead(db_session, account.id)
    call, _ = await _dial(client, db_session, agent, lead, "wacid.rej")
    await _post(client, _calls_event(number, statuses=[{"id": "wacid.rej", "type": "call", "status": "REJECTED"}]))
    assert (await _get_call(db_session, call.id)).status == "rejected"

    call2, _ = await _dial(client, db_session, agent, lead, "wacid.miss")
    await _post(client, _calls_event(number, calls=[_bic("wacid.miss", "terminate", status="COMPLETED")]))
    missed = await _get_call(db_session, call2.id)
    assert missed.status == "missed"
    conv = await db_session.get(Conversation, missed.conversation_id)
    assert not conv.unread_count  # ligação nossa não atendida não é mensagem nova do cliente


@pytest.mark.asyncio
async def test_hang_up_while_dialing_terminates_at_meta(client, db_session):
    account, _, _, agent, _ = await _tenant(db_session)
    lead = await _lead(db_session, account.id)
    call, _ = await _dial(client, db_session, agent, lead)

    with _FakeMeta() as meta:
        resp = await client.post(f"/api/v1/whatsapp/calls/{call.id}/terminate", headers=_headers(agent))
    assert resp.status_code == 200
    assert meta.bodies[0] == {"messaging_product": "whatsapp", "call_id": "wacid.out1", "action": "terminate"}
    assert (await _get_call(db_session, call.id)).status == "missed"


@pytest.mark.asyncio
async def test_other_tenant_cannot_call_my_lead(client, db_session):
    account, *_ = await _tenant(db_session)
    lead = await _lead(db_session, account.id)
    _, _, _, other_agent, _ = await _tenant(db_session)

    with _FakeMeta() as meta:
        resp = await client.post("/api/v1/whatsapp/calls/outbound", headers=_headers(other_agent),
                                 json={"lead_id": lead.id, "sdp": SDP_OFFER})
    assert resp.status_code == 404 and meta.requests == []


@pytest.mark.asyncio
async def test_routes_hidden_when_calling_disabled(client, db_session, monkeypatch):
    account, _, _, agent, _ = await _tenant(db_session)
    lead = await _lead(db_session, account.id)
    monkeypatch.setattr(settings, "whatsapp_calling_enabled", False)
    resp = await client.post("/api/v1/whatsapp/calls/outbound", headers=_headers(agent),
                             json={"lead_id": lead.id, "sdp": SDP_OFFER})
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_call_that_timed_out_does_not_block_the_next(client, db_session):
    from datetime import timedelta

    account, _, _, agent, _ = await _tenant(db_session)
    lead = await _lead(db_session, account.id)
    old, _ = await _dial(client, db_session, agent, lead, "wacid.old")
    old.ring_expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)
    await db_session.flush()

    call, _ = await _dial(client, db_session, agent, lead, "wacid.new")
    assert call.status == "dialing"
