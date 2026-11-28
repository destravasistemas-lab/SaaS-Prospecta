"""
Pix Automático da assinatura: o Asaas oferece na primeira cobrança, o webhook diz
quando o cliente autorizou, e com ele ativo a tela não pede para pagar de novo.
"""
import uuid
from unittest.mock import AsyncMock, patch

import pytest

from app.core.config import settings
from app.models.account import Account
from app.services import billing
from app.services.billing import seed_plans

WEBHOOK = "/api/v1/payments/webhook/asaas"
TOKEN = {"asaas-access-token": "tok"}


@pytest.fixture(autouse=True)
def _asaas_on(monkeypatch):
    monkeypatch.setattr(settings, "asaas_api_key", "k")
    monkeypatch.setattr(settings, "asaas_webhook_token", "tok")


def _asaas(sub_id, *, mode="OPTIONAL", authorization=None):
    payment = {"id": f"pay_{sub_id}", "status": "PENDING", "value": 297.0, "dueDate": "2026-11-28",
               "invoiceUrl": "https://asaas/i/1"}
    return {
        "create_customer": AsyncMock(return_value={"id": f"cus_{sub_id}"}),
        "create_subscription": AsyncMock(return_value={"id": sub_id, "pixAutomaticAuthorizationMode": mode}),
        "subscription_payments": AsyncMock(return_value=[payment]),
        "get_payment": AsyncMock(return_value=payment),
        "get_pix_qr": AsyncMock(return_value={"payload": "000201PIXAUTO", "encodedImage": "iVBOR"}),
        "cancel_subscription": AsyncMock(return_value={"deleted": True}),
        "subscription_pix_authorization": AsyncMock(return_value=authorization),
        "cancel_pix_authorization": AsyncMock(return_value={"status": "CANCELLED"}),
    }


def _patched(mocks):
    from contextlib import ExitStack
    stack = ExitStack()
    for name, mock in mocks.items():
        stack.enter_context(patch(f"app.routes.billing.asaas_service.{name}", mock))
    return stack


async def _subscribe(client, headers):
    r = await client.post("/api/v1/billing/subscribe",
                          json={"plan": "profissional", "name": "Clínica", "document": "12345678909"}, headers=headers)
    assert r.status_code == 200, r.text
    return r.json()


async def _hook(client, event, **body):
    r = await client.post(WEBHOOK, headers=TOKEN, json={"id": f"evt_{uuid.uuid4().hex}", "event": event, **body})
    assert r.status_code == 200


@pytest.mark.asyncio
async def test_offer_activation_auto_debit_and_refused_debit(client, db_session, make_user):
    await seed_plans(db_session)
    tid, headers = await make_user()
    sub_id = f"sub_{uuid.uuid4().hex[:8]}"
    mocks = _asaas(sub_id, authorization={"id": "auth_1", "status": "CREATED", "subscriptionId": sub_id})
    with _patched(mocks):
        data = await _subscribe(client, headers)
        assert data["pix_automatic"] == "CREATED"
        assert data["pending"]["pix_payload"] == "000201PIXAUTO" and data["pending"]["auto_debit"] is False
        acc = await db_session.get(Account, tid)
        assert acc.pix_auto_id == "auth_1"

        # Cliente pagou e autorizou no app do banco (webhook sem subscriptionId: acha pelo id)
        await _hook(client, "PIX_AUTOMATIC_RECURRING_AUTHORIZATION_ACTIVATED",
                    authorization={"id": "auth_1", "status": "ACTIVE", "customerId": f"cus_{sub_id}"})
        # Evento atrasado não volta o status para trás
        await _hook(client, "PIX_AUTOMATIC_RECURRING_AUTHORIZATION_CREATED",
                    authorization={"id": "auth_1", "status": "CREATED"})
        await db_session.refresh(acc)
        assert acc.pix_auto_status == "ACTIVE"

        data = (await client.get("/api/v1/billing/status", headers=headers)).json()
        assert data["pix_automatic"] == "ACTIVE" and data["pending"]["auto_debit"] is True
        mocks["subscription_pix_authorization"].assert_awaited_once()  # ativo: não consulta mais o Asaas

        # Banco recusou o débito: a cobrança volta a aparecer para pagar
        await _hook(client, "PIX_AUTOMATIC_RECURRING_PAYMENT_INSTRUCTION_REFUSED",
                    paymentInstruction={"id": "ins_1", "status": "REFUSED", "paymentId": f"pay_{sub_id}",
                                        "authorization": {"id": "auth_1"}})
        data = (await client.get("/api/v1/billing/status", headers=headers)).json()
        assert data["pending"]["auto_debit"] is False and data["pending"]["pix_payload"]

        # Cancelar a assinatura cancela também a autorização no Asaas
        r = await client.post("/api/v1/billing/cancel", headers=headers)
        assert r.status_code == 200 and r.json()["pix_automatic"] is None
        mocks["cancel_pix_authorization"].assert_awaited_once_with("auth_1")
        await db_session.refresh(acc)
        assert acc.pix_auto_id is None and acc.pix_auto_status is None


@pytest.mark.asyncio
async def test_not_offered_and_old_subscriptions(client, db_session, make_user):
    await seed_plans(db_session)
    _, headers = await make_user()
    mocks = _asaas(f"sub_{uuid.uuid4().hex[:8]}", mode="DISABLED")
    with _patched(mocks):
        assert (await _subscribe(client, headers))["pix_automatic"] == "DISABLED"
        mocks["subscription_pix_authorization"].assert_not_awaited()

    # Assinatura de antes do Pix Automático: consulta uma vez, não acha, fica DISABLED
    tid, headers = await make_user()
    acc = await db_session.get(Account, tid)
    acc.asaas_subscription_id = f"sub_{uuid.uuid4().hex[:8]}"
    await db_session.flush()
    mocks = _asaas(acc.asaas_subscription_id, authorization=None)
    with _patched(mocks):
        assert (await client.get("/api/v1/billing/status", headers=headers)).json()["pix_automatic"] == "DISABLED"
        await client.get("/api/v1/billing/status", headers=headers)
        mocks["subscription_pix_authorization"].assert_awaited_once()


@pytest.mark.asyncio
async def test_webhook_matches_by_customer_and_ignores_other_subscriptions(client, db_session, make_user):
    tid, _ = await make_user()
    acc = await db_session.get(Account, tid)
    acc.asaas_customer_id = f"cus_{uuid.uuid4().hex[:8]}"
    acc.asaas_subscription_id = f"sub_{uuid.uuid4().hex[:8]}"
    acc.pix_auto_status = "CREATED"
    await db_session.flush()

    # Autorização de uma assinatura antiga do mesmo cliente: ignorada
    await _hook(client, "PIX_AUTOMATIC_RECURRING_AUTHORIZATION_ACTIVATED",
                authorization={"id": "auth_old", "status": "ACTIVE", "subscriptionId": "sub_antiga",
                               "customerId": acc.asaas_customer_id})
    await db_session.refresh(acc)
    assert acc.pix_auto_status == "CREATED" and acc.pix_auto_id is None

    # Sem subscriptionId nem id conhecido: acha pelo cliente
    await _hook(client, "PIX_AUTOMATIC_RECURRING_AUTHORIZATION_ACTIVATED",
                authorization={"id": "auth_new", "customerId": acc.asaas_customer_id})
    await db_session.refresh(acc)
    assert acc.pix_auto_status == "ACTIVE" and acc.pix_auto_id == "auth_new"

    # Cliente cancelou no banco
    await _hook(client, "PIX_AUTOMATIC_RECURRING_AUTHORIZATION_CANCELLED",
                authorization={"id": "auth_new", "status": "CANCELLED", "cancellationReason": "REQUESTED_BY_PAYER_USER"})
    await db_session.refresh(acc)
    assert acc.pix_auto_status == "CANCELLED"

    # Token errado não muda nada
    r = await client.post(WEBHOOK, headers={"asaas-access-token": "x"}, json={
        "event": "PIX_AUTOMATIC_RECURRING_AUTHORIZATION_ACTIVATED", "authorization": {"id": "auth_new", "status": "ACTIVE"}})
    assert r.status_code == 200
    await db_session.refresh(acc)
    assert acc.pix_auto_status == "CANCELLED"


def test_apply_pix_authorization_rules():
    acc = Account(id="a", brand_name="x", asaas_subscription_id="sub_1")
    billing.pix_auto_from_subscription(acc, {"id": "sub_1"})
    assert acc.pix_auto_status == "DISABLED"
    billing.pix_auto_from_subscription(acc, {"id": "sub_1", "pixAutomaticAuthorizationMode": "OPTIONAL"})
    assert acc.pix_auto_status == "CREATED"
    assert billing.apply_pix_authorization(acc, {"id": "a1"}, "PIX_AUTOMATIC_RECURRING_AUTHORIZATION_EXPIRED")
    assert acc.pix_auto_status == "EXPIRED"
    assert not billing.apply_pix_authorization(acc, {"id": "a1", "status": "ACTIVE"})  # expirada não volta
    assert not billing.apply_pix_authorization(acc, {"id": "a2", "status": "WHATEVER", "subscriptionId": "sub_1"})
    assert billing.apply_pix_authorization(acc, {"id": "a2", "status": "CREATED", "subscriptionId": "sub_1"})
    assert (acc.pix_auto_id, acc.pix_auto_status) == ("a2", "CREATED")
