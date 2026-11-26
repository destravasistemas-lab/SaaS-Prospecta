"""
Sem opt-in: o sistema avisa os riscos e só envia se a empresa aceitar.
Opt-out continua bloqueado sempre. Envios sem opt-in ficam marcados na mensagem.
"""
from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy import select

from app.models.message import Message
from app.services import messaging_policy
from app.services.followup_service import run_due_followups

from tests.test_followup_flow import _mock_send, _setup
from tests.test_meta_compliance import _admin, _lead
from tests.test_whatsapp_flow import _wpp_tenant


def _tpl_mock():
    return patch("app.services.whatsapp_service.send_template", new_callable=AsyncMock,
                 return_value={"messages": [{"id": "wamid.RISK"}]})


@pytest.mark.asyncio
async def test_template_without_opt_in_warns_then_sends_when_risk_accepted(client, db_session):
    account, _ = await _wpp_tenant(db_session, "PNID_RISK1")
    headers = await _admin(db_session, account)
    lead = _lead(account.id, "5583900000101")
    db_session.add(lead)
    await db_session.flush()

    with _tpl_mock() as mock_tpl:
        r = await client.post("/api/v1/whatsapp/send-template",
                              json={"to": lead.phone, "template_name": "hello"}, headers=headers)
        assert r.status_code == 422
        assert r.json()["detail"]["can_accept_risk"] is True
        assert "banir" in r.json()["detail"]["message"]
        mock_tpl.assert_not_called()

        r = await client.post("/api/v1/whatsapp/send-template",
                              json={"to": lead.phone, "template_name": "hello", "accept_no_opt_in_risk": True},
                              headers=headers)
        assert r.status_code == 200
        mock_tpl.assert_called_once()
    await db_session.refresh(lead)
    assert lead.whatsapp_opt_in is False  # aceitar o risco não inventa consentimento


@pytest.mark.asyncio
async def test_opted_out_is_blocked_even_when_risk_accepted(client, db_session):
    account, _ = await _wpp_tenant(db_session, "PNID_RISK2")
    headers = await _admin(db_session, account)
    lead = _lead(account.id, "5583900000102", opt_in=True)
    messaging_policy.mark_opt_out(lead)
    db_session.add(lead)
    await db_session.flush()
    with _tpl_mock() as mock_tpl:
        r = await client.post("/api/v1/whatsapp/send-template",
                              json={"to": lead.phone, "template_name": "hello", "accept_no_opt_in_risk": True},
                              headers=headers)
        assert r.status_code == 409 and r.json()["detail"]["code"] == "opted_out"
        mock_tpl.assert_not_called()


@pytest.mark.asyncio
async def test_broadcast_can_include_contacts_without_opt_in(client, db_session):
    account, _ = await _wpp_tenant(db_session, "PNID_RISK3")
    headers = await _admin(db_session, account)
    opted = _lead(account.id, "5583900000111", opt_in=True)
    not_opted = _lead(account.id, "5583900000112")
    opted_out = _lead(account.id, "5583900000113", opt_in=True)
    messaging_policy.mark_opt_out(opted_out)
    db_session.add_all([opted, not_opted, opted_out])
    await db_session.flush()

    with _tpl_mock() as mock_tpl:
        r = await client.post("/api/v1/whatsapp/broadcast",
                              json={"template_name": "promo", "include_without_opt_in": True}, headers=headers)
    job = (await client.get(f"/api/v1/whatsapp/broadcast/jobs/{r.json()['id']}", headers=headers)).json()
    assert job["total"] == 2 and job["sent"] == 2
    assert sorted(c.args[2] for c in mock_tpl.call_args_list) == ["5583900000111", "5583900000112"]

    msgs = (await db_session.execute(
        select(Message).where(Message.tenant_id == account.id, Message.direction == "outbound")
    )).scalars().all()
    flagged = {m.wa_id for m in msgs if (m.payload or {}).get("sent_without_opt_in")}
    assert flagged == {"5583900000112"}


@pytest.mark.asyncio
async def test_followup_rule_can_include_contacts_without_opt_in(db_session):
    account, conv, lead, original, rule = await _setup(db_session, "PNID_RISK4", opt_in=False, phone="5583988882001")
    with _mock_send() as mock_send:
        assert await run_due_followups(db_session) == 0
        mock_send.assert_not_called()

    account, conv, lead, original, rule = await _setup(db_session, "PNID_RISK5", opt_in=False, phone="5583988882002")
    rule.include_without_opt_in = True
    await db_session.flush()
    with _mock_send() as mock_send:
        assert await run_due_followups(db_session) == 1
    fu = (await db_session.execute(
        select(Message).where(Message.conversation_id == conv.id, Message.sender == "followup")
    )).scalar_one()
    assert fu.payload["sent_without_opt_in"] is True
