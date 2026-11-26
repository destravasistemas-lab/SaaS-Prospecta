"""
Custo do WhatsApp: preço da Meta em R$ e US$ e contagem de mensagens cobradas
(uma vez por mensagem, na entrega, só quando a Meta marca como cobrada).
"""
import uuid

import pytest

from app.models.conversation import Conversation
from app.models.message import Message
from app.services import wpp_pricing

from tests.test_meta_compliance import _admin
from tests.test_whatsapp_flow import _signed_post, _wa_payload, _wpp_tenant

REGULAR = {"billable": True, "pricing_model": "PMP", "type": "regular", "category": "marketing"}
FREE_TIER = {"billable": False, "pricing_model": "PMP", "type": "free_customer_service",
             "category": "service", "subtype": "free_tier"}


def _status(wamid: str, status: str, pricing: dict) -> dict:
    return {"id": wamid, "status": status, "timestamp": "1700000000",
            "recipient_id": "5583900000001", "pricing": pricing}


def test_is_chargeable():
    assert wpp_pricing.is_chargeable(REGULAR)
    assert not wpp_pricing.is_chargeable(FREE_TIER)
    assert not wpp_pricing.is_chargeable({**REGULAR, "type": "free_entry_point"})
    # Payload antigo, sem type
    assert wpp_pricing.is_chargeable({"billable": True, "category": "utility"})


@pytest.mark.asyncio
async def test_message_counted_once_on_delivery(client, db_session):
    account, conn = await _wpp_tenant(db_session, "PNID_PRICE")
    conv = Conversation(id=str(uuid.uuid4()), tenant_id=account.id)
    db_session.add(conv)
    db_session.add(Message(tenant_id=account.id, conversation_id=conv.id, sender="disparo",
                           text="promo", direction="outbound", wa_id="5583900000001",
                           status="sent", message_id="wamid.P1"))
    await db_session.flush()

    for status in ("sent", "delivered", "read"):
        await _signed_post(client, _wa_payload("PNID_PRICE", statuses=[_status("wamid.P1", status, REGULAR)]))
    # Serviço dentro da franquia grátis: não conta
    await _signed_post(client, _wa_payload("PNID_PRICE", statuses=[_status("wamid.S1", "delivered", FREE_TIER)]))

    await db_session.refresh(conn)
    assert conn.conv_count_marketing == 1
    assert conn.conv_count_service == 0


@pytest.mark.asyncio
async def test_costs_in_brl_and_usd(client, db_session):
    account, conn = await _wpp_tenant(db_session, "PNID_COSTS")
    conn.conv_count_marketing = 100
    conn.conv_count_utility = 10
    await db_session.flush()
    headers = await _admin(db_session, account)

    body = (await client.get("/api/v1/whatsapp/costs", headers=headers)).json()
    mk = body["breakdown"]["marketing"]
    assert mk["unit_cost"] == wpp_pricing.unit("marketing", "brl")
    assert mk["unit_cost_usd"] == wpp_pricing.unit("marketing", "usd")
    assert mk["subtotal"] == round(100 * wpp_pricing.unit("marketing", "brl"), 2)
    assert mk["subtotal_usd"] == round(100 * wpp_pricing.unit("marketing", "usd"), 2)
    assert body["total_usd"] == round(mk["subtotal_usd"] + body["breakdown"]["utility"]["subtotal_usd"], 2)
    assert body["pricing_usd"]["utility"] == wpp_pricing.unit("utility", "usd")
    assert body["prices_effective_from"] == wpp_pricing.EFFECTIVE_FROM
