"""
IA do Prospecta: chave da plataforma ou própria, fila de vazão (Redis/memória),
troca de chave no 429, franquia do plano + pacotes e o painel do super admin.
"""
import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy import select

from app.core import redis as redis_mod
from app.core.config import settings
from app.models.account import Account
from app.models.ai import AIConfig, AIUsageDay
from app.models.billing import AIPackPurchase, Plan
from app.models.conversation import Conversation
from app.models.message import Message
from app.models.user import User
from app.services import ai_agent, ai_platform
from app.services.billing import seed_plans
from app.services.gemini_service import GeminiRateLimited
from app.services.meta_token_service import encrypt_token

from tests.test_whatsapp_flow import _wpp_tenant


@pytest.fixture(autouse=True)
def _fresh(monkeypatch):
    redis_mod._memory.clear()
    monkeypatch.setattr(settings, "gemini_api_keys", "KEY_A,KEY_B")
    monkeypatch.setattr(settings, "ai_slot_wait_seconds", 1.5)
    yield
    redis_mod._memory.clear()


async def _conversation(db_session, pnid, *, plan=None, extra=0, own_key=False):
    account, conn = await _wpp_tenant(db_session, pnid)
    account.billing_plan = plan
    account.ai_extra_tokens = extra
    cfg = AIConfig(account_id=account.id, enabled=True, system_prompt="Atenda a clínica.",
                   gemini_api_key_encrypted=encrypt_token("OWN") if own_key else None, use_own_key=own_key,
                   month_ref=ai_platform.month_ref())
    db_session.add(cfg)
    conv = Conversation(id=str(uuid.uuid4()), tenant_id=account.id, bot_active=True, status="active")
    db_session.add(conv)
    await db_session.flush()
    db_session.add(Message(tenant_id=account.id, conversation_id=conv.id, sender="5583999990000", text="Quanto custa?",
                           direction="inbound", wa_id="5583999990000", status="delivered", message_id=f"wamid.{uuid.uuid4()}",
                           created_at=datetime.now(timezone.utc)))
    await db_session.flush()
    return account, conn, cfg, conv


def _send_ok():
    return patch("app.services.whatsapp_service.send_text", new_callable=AsyncMock,
                 return_value={"messages": [{"id": "wamid.AI"}]})


def _quiet():
    return (patch("app.services.whatsapp_service.send_typing_indicator", new_callable=AsyncMock),
            patch("app.services.whatsapp_service.mark_as_read", new_callable=AsyncMock),
            patch("app.services.gemini_service.embed_query", new_callable=AsyncMock, return_value=[]))


@pytest.mark.asyncio
async def test_platform_key_answers_and_429_moves_to_the_other_key(db_session):
    await seed_plans(db_session)
    account, _, cfg, conv = await _conversation(db_session, "PN_AI1", plan="profissional")
    used_keys = []

    async def fake_generate(api_key, system, contents, temperature=0.4, usage_out=None, **kw):
        used_keys.append(api_key)
        if len(used_keys) == 1:
            raise GeminiRateLimited("quota")
        usage_out.update({"input": 2800, "output": 200})
        return "Custa R$ 200.", 3000

    q = _quiet()
    with q[0], q[1], q[2], _send_ok() as send, patch("app.services.gemini_service.generate_content", side_effect=fake_generate):
        await ai_agent.reply_to_conversation(db_session, account.id, conv.id)

    assert send.call_args.args[3] == "Custa R$ 200."
    assert len(used_keys) == 2 and used_keys[0] != used_keys[1]
    assert set(used_keys) == {"KEY_A", "KEY_B"}
    assert cfg.platform_tokens_month == 3000
    day = (await db_session.execute(select(AIUsageDay).where(AIUsageDay.account_id == account.id))).scalar_one()
    assert (day.input_tokens, day.output_tokens, day.platform_tokens, day.rate_limited) == (2800, 200, 3000, 1)


@pytest.mark.asyncio
async def test_own_key_does_not_touch_the_platform_allowance(db_session):
    account, _, cfg, conv = await _conversation(db_session, "PN_AI2", own_key=True)
    q = _quiet()
    with q[0], q[1], q[2], _send_ok(), patch("app.services.gemini_service.generate_content", new_callable=AsyncMock,
                                             return_value=("Oi!", 1000)) as gen:
        await ai_agent.reply_to_conversation(db_session, account.id, conv.id)
    assert gen.call_args.args[0] == "OWN"
    assert cfg.platform_tokens_month == 0 and cfg.tokens_used_month == 1000


@pytest.mark.asyncio
async def test_allowance_then_extra_pack_then_human_queue(db_session):
    await seed_plans(db_session)
    plan = await db_session.get(Plan, "essencial")
    plan.limits = {**plan.limits, "ai_tokens": 4000}
    account, _, cfg, conv = await _conversation(db_session, "PN_AI3", plan="essencial", extra=2000)

    q = _quiet()
    with q[0], q[1], q[2], _send_ok(), patch("app.services.gemini_service.generate_content", new_callable=AsyncMock,
                                             return_value=("Resposta", 5000)):
        await ai_agent.reply_to_conversation(db_session, account.id, conv.id)
    # Passou 1000 da franquia: saiu do saldo do pacote
    assert account.ai_extra_tokens == 1000
    allowance = await ai_platform.allowance(db_session, account.id)
    assert allowance.used == 5000 and allowance.remaining == 0

    db_session.add(Message(tenant_id=account.id, conversation_id=conv.id, sender="5583999990000", text="E agora?",
                           direction="inbound", wa_id="5583999990000", status="delivered", message_id="wamid.X2",
                           created_at=datetime.now(timezone.utc) + timedelta(seconds=5)))
    await db_session.flush()
    with q[0], q[1], q[2], _send_ok(), patch("app.services.gemini_service.generate_content", new_callable=AsyncMock) as gen:
        await ai_agent.reply_to_conversation(db_session, account.id, conv.id)
    gen.assert_not_called()
    assert conv.bot_active is False and conv.atendimento_status == "aguardando"


@pytest.mark.asyncio
async def test_agency_and_children_share_the_allowance(db_session):
    await seed_plans(db_session)
    parent, _, cfg_parent, _ = await _conversation(db_session, "PN_AI4", plan="agencia")
    child = Account(id=str(uuid.uuid4()), brand_name="Filha", plan_type="dependente", parent_account_id=parent.id)
    db_session.add(child)
    db_session.add(AIConfig(account_id=child.id, enabled=True, platform_tokens_month=7000, month_ref=ai_platform.month_ref()))
    cfg_parent.platform_tokens_month = 3000
    await db_session.flush()
    a = await ai_platform.allowance(db_session, child.id)
    assert a.used == 10_000 and a.included == 60_000_000 and a.billing_account_id == parent.id


@pytest.mark.asyncio
async def test_queue_waits_and_gives_up_when_the_account_is_over_its_rate(monkeypatch):
    monkeypatch.setattr(settings, "ai_account_rpm", 1)
    first, wait1 = await ai_platform.acquire_slot("acc-q", own_key=False)
    assert first in (0, 1) and wait1 < 500
    second, wait2 = await ai_platform.acquire_slot("acc-q", own_key=False)
    assert second is None and wait2 >= 1000
    # Outra conta não é afetada
    other, _ = await ai_platform.acquire_slot("acc-other", own_key=False)
    assert other is not None


@pytest.mark.asyncio
async def test_cooled_key_is_skipped():
    await ai_platform.cool_down(0)
    for _ in range(5):
        slot, _ = await ai_platform.acquire_slot(f"acc-{uuid.uuid4()}", own_key=False)
        assert slot == 1


@pytest.mark.asyncio
async def test_config_uses_platform_or_own_key(client, make_user, monkeypatch):
    _, headers = await make_user()
    r = await client.put("/api/v1/ai/config", json={"enabled": True}, headers=headers)
    assert r.status_code == 200 and r.json()["enabled"] and r.json()["platform_available"]
    assert r.json()["use_own_key"] is False
    r = await client.put("/api/v1/ai/config", json={"use_own_key": True}, headers=headers)
    assert r.status_code == 422
    r = await client.put("/api/v1/ai/config", json={"gemini_api_key": "MINHA"}, headers=headers)
    assert r.json()["use_own_key"] is True
    r = await client.put("/api/v1/ai/config", json={"use_own_key": False}, headers=headers)
    assert r.json()["use_own_key"] is False and r.json()["has_api_key"] is True

    monkeypatch.setattr(settings, "gemini_api_keys", "")
    _, headers2 = await make_user()
    r = await client.put("/api/v1/ai/config", json={"enabled": True}, headers=headers2)
    assert r.status_code == 422


@pytest.mark.asyncio
async def test_plans_show_conversations_and_old_defaults_are_upgraded(client, db_session):
    db_session.add(Plan(code="essencial", name="Essencial", price_cents=14700,
                        limits={"users": 2, "clients": 0, "ai_tokens": 1_000_000}, modules=["whatsapp"], extras=[]))
    db_session.add(Plan(code="profissional", name="Profissional", price_cents=29700,
                        limits={"users": 5, "clients": 0, "ai_tokens": 4_000_000}, modules=["whatsapp"], extras=[]))
    await db_session.flush()
    await seed_plans(db_session)
    assert (await db_session.get(Plan, "essencial")).limits["ai_tokens"] == 6_000_000
    assert (await db_session.get(Plan, "profissional")).limits["ai_tokens"] == 4_000_000  # editado pelo dono: não mexe
    plans = {p["code"]: p for p in (await client.get("/api/v1/billing/plans")).json()}
    assert plans["essencial"]["ai_conversations"] == 300


@pytest.mark.asyncio
async def test_ai_pack_paid_by_webhook_credits_tokens(client, db_session, make_user, monkeypatch):
    monkeypatch.setattr(settings, "asaas_api_key", "k")
    monkeypatch.setattr(settings, "asaas_webhook_token", "tok")
    tid, headers = await make_user()
    with patch("app.routes.billing.asaas_service.create_customer", new_callable=AsyncMock, return_value={"id": "cus_9"}), \
         patch("app.routes.billing.asaas_service.create_payment", new_callable=AsyncMock, return_value={"id": "pay_pack"}) as pay, \
         patch("app.routes.billing.asaas_service.get_payment", new_callable=AsyncMock,
               return_value={"id": "pay_pack", "status": "PENDING", "invoiceUrl": "https://asaas/i/p"}), \
         patch("app.routes.billing.asaas_service.get_pix_qr", new_callable=AsyncMock, return_value={"payload": "PIXPACK"}):
        assert (await client.post("/api/v1/billing/ai-pack", json={}, headers=headers)).status_code == 422
        r = await client.post("/api/v1/billing/ai-pack", json={"name": "Clínica", "document": "12345678909"}, headers=headers)
        assert r.status_code == 200 and r.json()["pending"]["pix_payload"] == "PIXPACK"
        assert pay.call_args.kwargs["value"] == settings.ai_pack_price_cents / 100
    w = await client.post("/api/v1/payments/webhook/asaas", headers={"asaas-access-token": "tok"},
                          json={"event": "PAYMENT_RECEIVED", "payment": {"id": "pay_pack"}})
    assert w.status_code == 200
    acc = await db_session.get(Account, tid)
    await db_session.refresh(acc)
    assert acc.ai_extra_tokens == settings.ai_pack_conversations * settings.ai_tokens_per_conversation
    purchase = (await db_session.execute(select(AIPackPurchase).where(AIPackPurchase.account_id == tid))).scalar_one()
    assert purchase.status == "paid"


@pytest.mark.asyncio
async def test_super_admin_ai_usage(client, db_session, make_user, monkeypatch):
    _, headers = await make_user()
    admin = (await db_session.execute(select(User).order_by(User.created_at.desc()).limit(1))).scalar_one()
    monkeypatch.setattr(settings, "super_admin_emails", admin.username)
    tid, _ = await make_user()
    db_session.add(AIUsageDay(account_id=tid, day=datetime.now(timezone.utc).date(), tokens=1_000_000, messages=50,
                              fallbacks=2, input_tokens=900_000, output_tokens=100_000, platform_tokens=1_000_000,
                              rate_limited=3, queue_wait_ms=5000))
    await db_session.flush()
    r = await client.get("/api/v1/admin/ai-usage?days=7", headers=headers)
    assert r.status_code == 200
    data = r.json()
    assert data["keys"] == 2 and data["totals"]["rate_limited"] == 3 and data["totals"]["replies"] == 50
    expected = round((900_000 * settings.ai_price_input_usd_per_m + 100_000 * settings.ai_price_output_usd_per_m) / 1e6 * settings.usd_brl, 2)
    assert data["totals"]["cost_brl"] == expected
    assert data["accounts"][0]["conversations"] == 50
