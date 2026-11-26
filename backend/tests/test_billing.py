"""
Cobrança do Prospecta: acesso (teste, pago, tolerância, cortesia), bloqueio com
BILLING_ENFORCED, assinatura no Asaas, webhook, super admin e limites do plano.
"""
import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy import select

from app.core.config import settings
from app.models.account import Account, APPROVAL_PENDING
from app.models.billing import Plan
from app.models.user import User
from app.services import billing
from app.services.billing import compute_access, seed_plans

NOW = datetime(2026, 11, 25, 12, tzinfo=timezone.utc)


def _acc(**kw):
    return Account(id=str(uuid.uuid4()), brand_name="x", **kw)


def test_access_rules(monkeypatch):
    monkeypatch.setattr(settings, "billing_grace_days", 3)
    assert compute_access(_acc(), NOW).status == "unmanaged"
    assert compute_access(_acc(billing_status="courtesy"), NOW).allowed
    expired = compute_access(_acc(billing_status="courtesy", courtesy_until=NOW - timedelta(days=1)), NOW)
    assert expired.status == "blocked" and not expired.allowed
    assert compute_access(_acc(billing_status="active", paid_until=NOW + timedelta(days=5)), NOW).status == "active"
    late = compute_access(_acc(billing_status="past_due", paid_until=NOW - timedelta(days=2)), NOW)
    assert late.status == "past_due" and late.allowed
    assert not compute_access(_acc(billing_status="past_due", paid_until=NOW - timedelta(days=4)), NOW).allowed
    assert compute_access(_acc(billing_status="trial", trial_ends_at=NOW + timedelta(days=1)), NOW).status == "trial"
    assert not compute_access(_acc(billing_status="trial", trial_ends_at=NOW - timedelta(hours=1)), NOW).allowed


def test_paid_until_is_one_month_after_due_date():
    acc = _acc(billing_status="trial")
    billing.apply_paid(acc, "2026-01-31", "pay_1")
    assert acc.paid_until.date().isoformat() == "2026-02-28" and acc.billing_status == "active"
    billing.apply_paid(acc, "2026-01-31", "pay_1")  # webhook repetido não estende de novo
    assert acc.paid_until.date().isoformat() == "2026-02-28"


async def _blocked_user(db_session, make_user):
    tid, headers = await make_user()
    acc = await db_session.get(Account, tid)
    acc.billing_status = "trial"
    acc.trial_ends_at = datetime.now(timezone.utc) - timedelta(days=1)
    await db_session.flush()
    return tid, headers


@pytest.mark.asyncio
async def test_not_enforced_means_nobody_is_blocked(client, db_session, make_user):
    _, headers = await _blocked_user(db_session, make_user)
    assert (await client.get("/api/v1/leads", headers=headers)).status_code == 200


@pytest.mark.asyncio
async def test_enforced_blocks_everything_but_plans(client, db_session, make_user, monkeypatch):
    monkeypatch.setattr(settings, "billing_enforced", True)
    tid, headers = await _blocked_user(db_session, make_user)
    r = await client.get("/api/v1/leads", headers=headers)
    assert r.status_code == 402 and r.json()["detail"]["code"] == "billing_required"
    assert (await client.get("/api/v1/billing/status", headers=headers)).json()["status"] == "blocked"
    me = (await client.get("/api/v1/auth/me", headers=headers)).json()
    assert me["billing"]["allowed"] is False and me["billing"]["enforced"] is True

    # Empresa-filha segue a agência
    child = Account(id=str(uuid.uuid4()), brand_name="filha", plan_type="dependente", parent_account_id=tid)
    db_session.add(child)
    await db_session.flush()
    _, child_headers = await make_user(tenant_id=child.id)
    assert (await client.get("/api/v1/leads", headers=child_headers)).status_code == 402

    # Super admin nunca é bloqueado
    user = (await db_session.execute(select(User).where(User.tenant_id == tid))).scalar_one()
    monkeypatch.setattr(settings, "super_admin_emails", user.username)
    assert (await client.get("/api/v1/leads", headers=headers)).status_code == 200


@pytest.mark.asyncio
async def test_approval_starts_the_trial(client, db_session, make_user, monkeypatch):
    _, admin_headers = await make_user()
    admin = (await db_session.execute(select(User).order_by(User.created_at.desc()).limit(1))).scalar_one()
    monkeypatch.setattr(settings, "super_admin_emails", admin.username)
    new = Account(id=str(uuid.uuid4()), brand_name="Nova", approval_status=APPROVAL_PENDING)
    db_session.add(new)
    await db_session.flush()
    r = await client.post(f"/api/v1/admin/tenants/{new.id}/approval", json={"approved": True}, headers=admin_headers)
    assert r.status_code == 200
    assert r.json()["billing"]["status"] == "trial"
    assert new.billing_plan == settings.billing_trial_plan
    assert 6 <= (billing._aware(new.trial_ends_at) - datetime.now(timezone.utc)).days <= 7


def _asaas():
    return (
        patch("app.routes.billing.asaas_service.create_customer", new_callable=AsyncMock, return_value={"id": "cus_1"}),
        patch("app.routes.billing.asaas_service.create_subscription", new_callable=AsyncMock, return_value={"id": "sub_1"}),
        patch("app.routes.billing.asaas_service.subscription_payments", new_callable=AsyncMock,
              return_value=[{"id": "pay_1", "status": "PENDING"}]),
        patch("app.routes.billing.asaas_service.get_payment", new_callable=AsyncMock,
              return_value={"id": "pay_1", "status": "PENDING", "value": 297.0, "dueDate": "2026-11-25",
                            "invoiceUrl": "https://asaas/i/1"}),
        patch("app.routes.billing.asaas_service.get_pix_qr", new_callable=AsyncMock,
              return_value={"payload": "000201PIX", "encodedImage": "iVBOR"}),
        patch("app.routes.billing.asaas_service.cancel_subscription", new_callable=AsyncMock, return_value={"deleted": True}),
    )


@pytest.mark.asyncio
async def test_subscribe_pay_by_webhook_and_cancel(client, db_session, make_user, monkeypatch):
    monkeypatch.setattr(settings, "asaas_api_key", "k")
    monkeypatch.setattr(settings, "asaas_webhook_token", "tok")
    await seed_plans(db_session)
    tid, headers = await _blocked_user(db_session, make_user)
    plans = (await client.get("/api/v1/billing/plans")).json()
    assert [p["code"] for p in plans] == ["essencial", "profissional", "agencia"]

    m = _asaas()
    with m[0] as cust, m[1] as sub, m[2], m[3], m[4], m[5] as cancel:
        r = await client.post("/api/v1/billing/subscribe",
                              json={"plan": "profissional", "name": "Clínica", "document": "123.456.789-09"}, headers=headers)
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["pending"]["pix_payload"] == "000201PIX" and data["pending"]["invoice_url"] == "https://asaas/i/1"
        assert cust.call_args.kwargs["cpf_cnpj"] == "12345678909"
        assert sub.call_args.args[1] == 297.0
        acc = await db_session.get(Account, tid)
        assert acc.asaas_subscription_id == "sub_1" and acc.billing_plan == "profissional"

        w = await client.post("/api/v1/payments/webhook/asaas", headers={"asaas-access-token": "tok"}, json={
            "event": "PAYMENT_RECEIVED", "payment": {"id": "pay_1", "subscription": "sub_1", "dueDate": "2026-11-25"},
        })
        assert w.status_code == 200
        await db_session.refresh(acc)
        assert acc.billing_status == "active" and acc.paid_until.date().isoformat() == "2026-12-25"
        assert acc.pending_payment_id is None

        r = await client.post("/api/v1/billing/cancel", headers=headers)
        assert r.status_code == 200
        cancel.assert_awaited_once_with("sub_1")
        await db_session.refresh(acc)
        assert acc.asaas_subscription_id is None and acc.billing_status == "canceled"
        assert acc.paid_until is not None  # acesso vai até o fim do período pago


@pytest.mark.asyncio
async def test_subscribe_validation(client, db_session, make_user, monkeypatch):
    await seed_plans(db_session)
    _, headers = await make_user()
    body = {"plan": "profissional", "name": "X Y", "document": "12345678909"}
    assert (await client.post("/api/v1/billing/subscribe", json=body, headers=headers)).status_code == 503
    monkeypatch.setattr(settings, "asaas_api_key", "k")
    assert (await client.post("/api/v1/billing/subscribe", json={**body, "document": "123"}, headers=headers)).status_code == 422
    assert (await client.post("/api/v1/billing/subscribe", json={**body, "plan": "nao_existe"}, headers=headers)).status_code == 404
    _, agent_headers = await make_user(role="agent")
    assert (await client.post("/api/v1/billing/subscribe", json=body, headers=agent_headers)).status_code == 403


@pytest.mark.asyncio
async def test_old_free_upgrade_routes_are_closed(client, make_user):
    _, headers = await make_user()
    r = await client.post("/api/v1/payments/subscribe", json={"plan": "premium"}, headers=headers)
    assert r.status_code in (410, 422)
    r = await client.post("/api/v1/payments/upgrade?new_plan=premium", headers=headers)
    assert r.status_code == 410


@pytest.mark.asyncio
async def test_super_admin_courtesy_trial_and_plans(client, db_session, make_user, monkeypatch):
    await seed_plans(db_session)
    _, admin_headers = await make_user()
    admin = (await db_session.execute(select(User).order_by(User.created_at.desc()).limit(1))).scalar_one()
    monkeypatch.setattr(settings, "super_admin_emails", admin.username)
    tid, headers = await _blocked_user(db_session, make_user)
    url = f"/api/v1/admin/tenants/{tid}/billing"

    r = await client.post(url, json={"action": "courtesy", "until": "2099-01-31", "plan": "agencia", "note": "Parceiro"},
                          headers=admin_headers)
    assert r.status_code == 200 and r.json()["billing"]["status"] == "courtesy"
    acc = await db_session.get(Account, tid)
    assert acc.billing_plan == "agencia" and acc.billing_note == "Parceiro"
    assert acc.courtesy_until.date().isoformat() == "2099-01-31"

    r = await client.post(url, json={"action": "end_courtesy"}, headers=admin_headers)
    assert r.json()["billing"]["status"] == "blocked"
    r = await client.post(url, json={"action": "trial", "days": 14}, headers=admin_headers)
    assert r.json()["billing"]["status"] == "trial" and r.json()["billing"]["days_left"] >= 13

    assert (await client.post(url, json={"action": "trial"}, headers=headers)).status_code == 403

    r = await client.put("/api/v1/admin/plans/essencial", headers=admin_headers, json={
        "name": "Essencial", "price_cents": 9700, "limits": {"users": 3, "clients": 0, "ai_tokens": None, "outro": 5},
        "modules": ["whatsapp", "nada"], "extras": ["Suporte por e-mail", " "], "highlight": False, "active": True, "sort": 1,
    })
    assert r.status_code == 200
    plan = await db_session.get(Plan, "essencial")
    assert plan.price_cents == 9700 and plan.modules == ["whatsapp"] and plan.extras == ["Suporte por e-mail"]
    assert plan.limits == {"users": 3, "clients": 0, "ai_tokens": None}
    r = await client.put("/api/v1/admin/plans/novo_plano", headers=admin_headers,
                         json={"name": "Novo", "price_cents": 100, "active": False})
    assert r.status_code == 200
    assert "novo_plano" not in [p["code"] for p in (await client.get("/api/v1/billing/plans")).json()]


@pytest.mark.asyncio
async def test_plan_limits_apply_only_when_enforced(client, db_session, make_user, monkeypatch):
    await seed_plans(db_session)
    tid, headers = await make_user()
    acc = await db_session.get(Account, tid)
    acc.billing_status = "active"
    acc.paid_until = datetime.now(timezone.utc) + timedelta(days=10)
    acc.billing_plan = "essencial"  # 2 usuários, sem anúncios
    await db_session.flush()
    new_user = {"username": f"{uuid.uuid4()}@t.com", "password": "senha123", "full_name": "A", "role": "agent"}

    assert (await client.post("/api/v1/auth/users", json=new_user, headers=headers)).status_code == 201
    me = (await client.get("/api/v1/auth/me", headers=headers)).json()
    assert "ads" in me["modules"]

    monkeypatch.setattr(settings, "billing_enforced", True)
    r = await client.post("/api/v1/auth/users", json={**new_user, "username": f"{uuid.uuid4()}@t.com"}, headers=headers)
    assert r.status_code == 403 and r.json()["detail"]["code"] == "plan_limit"
    me = (await client.get("/api/v1/auth/me", headers=headers)).json()
    assert "ads" not in me["modules"] and "whatsapp" in me["modules"]
    assert (await client.get("/api/v1/marketing/campaigns", headers=headers)).status_code == 403
