"""
Template direto da lista de Leads: usa o telefone do lead, a mensagem entra na
conversa de WhatsApp dele (criada se ele nunca conversou) e o lead vira "contatado".
"""
import uuid
from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy import select

from app.models.conversation import Conversation
from app.models.message import Message
from app.services import messaging_policy

from tests.test_meta_compliance import _admin, _lead
from tests.test_whatsapp_flow import _wpp_tenant


def _tpl_mock():
    return patch("app.services.whatsapp_service.send_template", new_callable=AsyncMock,
                 side_effect=lambda *a, **k: {"messages": [{"id": f"wamid.{uuid.uuid4().hex}"}]})


@pytest.mark.asyncio
async def test_send_template_to_lead_without_conversation(client, db_session):
    account, _ = await _wpp_tenant(db_session, "PNID_LEADTPL1")
    headers = await _admin(db_session, account)
    lead = _lead(account.id, "5583900000201", opt_in=True)
    # Lead mesclado: já tem conversa no Instagram, que não pode receber o template
    ig_conv = Conversation(id=str(uuid.uuid4()), tenant_id=account.id, customer_id=lead.id,
                           channel="instagram", status="active", atendimento_status="aberto")
    db_session.add_all([lead, ig_conv])
    await db_session.flush()

    with _tpl_mock() as mock_tpl:
        r = await client.post("/api/v1/whatsapp/send-template", headers=headers, json={
            "lead_id": lead.id, "template_name": "boas_vindas", "variables": ["Ana"]})
        assert r.status_code == 200, r.text
        assert mock_tpl.call_args.args[2] == "5583900000201"

        # Segundo envio reaproveita a mesma conversa
        r = await client.post("/api/v1/whatsapp/send-template", headers=headers, json={
            "lead_id": lead.id, "template_name": "lembrete"})
        assert r.status_code == 200

    convs = (await db_session.execute(
        select(Conversation).where(Conversation.customer_id == lead.id, Conversation.channel == "whatsapp")
    )).scalars().all()
    assert len(convs) == 1
    msgs = (await db_session.execute(
        select(Message).where(Message.conversation_id == convs[0].id).order_by(Message.created_at)
    )).scalars().all()
    assert [m.template_name for m in msgs] == ["boas_vindas", "lembrete"]
    assert all(m.wa_id == "5583900000201" for m in msgs)
    assert (await db_session.execute(
        select(Message).where(Message.conversation_id == ig_conv.id))).first() is None
    await db_session.refresh(lead)
    assert lead.status == "contacted"


@pytest.mark.asyncio
async def test_send_template_to_lead_keeps_consent_rules(client, db_session):
    account, _ = await _wpp_tenant(db_session, "PNID_LEADTPL2")
    headers = await _admin(db_session, account)
    no_opt_in = _lead(account.id, "5583900000202")
    opted_out = _lead(account.id, "5583900000203", opt_in=True)
    messaging_policy.mark_opt_out(opted_out)
    no_phone = _lead(account.id, "x")
    no_phone.phone = None
    db_session.add_all([no_opt_in, opted_out, no_phone])
    await db_session.flush()

    with _tpl_mock() as mock_tpl:
        r = await client.post("/api/v1/whatsapp/send-template", headers=headers,
                              json={"lead_id": no_opt_in.id, "template_name": "oi"})
        assert r.status_code == 422 and r.json()["detail"]["can_accept_risk"] is True
        r = await client.post("/api/v1/whatsapp/send-template", headers=headers,
                              json={"lead_id": opted_out.id, "template_name": "oi", "accept_no_opt_in_risk": True})
        assert r.status_code in (403, 409, 422) and not (r.json().get("detail") or {}).get("can_accept_risk")
        r = await client.post("/api/v1/whatsapp/send-template", headers=headers,
                              json={"lead_id": no_phone.id, "template_name": "oi"})
        assert r.status_code == 422
        mock_tpl.assert_not_called()
    # Nada foi criado para quem não recebeu
    assert (await db_session.execute(
        select(Conversation).where(Conversation.customer_id.in_([no_opt_in.id, opted_out.id, no_phone.id]))
    )).first() is None


@pytest.mark.asyncio
async def test_send_template_to_lead_of_another_company_is_404(client, db_session):
    account, _ = await _wpp_tenant(db_session, "PNID_LEADTPL3")
    other, _ = await _wpp_tenant(db_session, "PNID_LEADTPL4")
    headers = await _admin(db_session, account)
    lead = _lead(other.id, "5583900000204", opt_in=True)
    db_session.add(lead)
    await db_session.flush()
    with _tpl_mock() as mock_tpl:
        r = await client.post("/api/v1/whatsapp/send-template", headers=headers,
                              json={"lead_id": lead.id, "template_name": "oi"})
        assert r.status_code == 404
        mock_tpl.assert_not_called()
