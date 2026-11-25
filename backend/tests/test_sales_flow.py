"""
"Fechou venda": registra a venda no lead, alimenta a receita do dashboard
(só da própria conta) e tira o lead do follow-up automático.
"""
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import select

from app.models.automation import Customer, Sale
from app.models.followup import FollowUpDispatch
from app.models.lead import Lead, LeadStatus
from app.services.followup_service import run_due_followups

from tests.test_followup_flow import _mock_send, _setup


async def _lead(client, headers, phone):
    resp = await client.post("/api/v1/leads", json={"name": "Bia", "phone": phone}, headers=headers)
    assert resp.status_code == 201
    return resp.json()["id"]


@pytest.mark.asyncio
async def test_close_sale_converts_lead_and_feeds_revenue(client, db_session, make_user):
    tid, headers = await make_user()
    lead_id = await _lead(client, headers, "83 97777-0001")

    r = await client.post(f"/api/v1/leads/{lead_id}/sales",
                          json={"amount": 1500.5, "description": "Plano anual"}, headers=headers)
    assert r.status_code == 201
    assert r.json()["lead_status"] == "converted"
    assert r.json()["total"] == 1500.5

    # Segunda venda reaproveita o mesmo cliente
    r = await client.post(f"/api/v1/leads/{lead_id}/sales", json={"amount": 499.5}, headers=headers)
    assert r.json()["total"] == 2000.0 and len(r.json()["sales"]) == 2
    customers = (await db_session.execute(select(Customer).where(Customer.lead_id == lead_id))).scalars().all()
    assert len(customers) == 1 and customers[0].account_id == tid

    dash = (await client.get("/api/v1/dashboard", headers=headers)).json()
    assert dash["total_revenue"] == 2000.0
    assert dash["monthly_revenue"] == 2000.0
    assert dash["total_customers"] == 1
    assert dash["average_ticket"] == 1000.0


@pytest.mark.asyncio
async def test_revenue_is_isolated_per_account(client, make_user):
    _, headers_a = await make_user()
    _, headers_b = await make_user()
    lead_a = await _lead(client, headers_a, "83 97777-0002")
    await client.post(f"/api/v1/leads/{lead_a}/sales", json={"amount": 300}, headers=headers_a)

    dash_b = (await client.get("/api/v1/dashboard", headers=headers_b)).json()
    assert dash_b["total_revenue"] == 0 and dash_b["total_customers"] == 0
    assert dash_b["new_customers_30d"] == 0

    # Conta B não lança nem lê venda em lead da conta A
    assert (await client.post(f"/api/v1/leads/{lead_a}/sales", json={"amount": 1}, headers=headers_b)).status_code == 404
    assert (await client.get(f"/api/v1/leads/{lead_a}/sales", headers=headers_b)).status_code == 404


@pytest.mark.asyncio
async def test_cancel_sale_reverts_lead_and_revenue(client, make_user):
    _, headers = await make_user()
    lead_id = await _lead(client, headers, "83 97777-0003")
    sale_id = (await client.post(f"/api/v1/leads/{lead_id}/sales", json={"amount": 80}, headers=headers)).json()["sales"][0]["id"]

    r = await client.post(f"/api/v1/leads/{lead_id}/sales/{sale_id}/cancel", headers=headers)
    assert r.status_code == 200
    assert r.json()["total"] == 0 and r.json()["lead_status"] == "qualified"
    assert (await client.get("/api/v1/dashboard", headers=headers)).json()["total_revenue"] == 0


@pytest.mark.asyncio
async def test_invalid_amount_rejected(client, make_user):
    _, headers = await make_user()
    lead_id = await _lead(client, headers, "83 97777-0004")
    for bad in (0, -10):
        r = await client.post(f"/api/v1/leads/{lead_id}/sales", json={"amount": bad}, headers=headers)
        assert r.status_code == 422


@pytest.mark.asyncio
async def test_deleting_lead_keeps_sale_in_revenue(client, db_session, make_user):
    _, headers = await make_user()
    lead_id = await _lead(client, headers, "83 97777-0005")
    await client.post(f"/api/v1/leads/{lead_id}/sales", json={"amount": 250}, headers=headers)
    assert (await client.delete(f"/api/v1/leads/{lead_id}", headers=headers)).status_code == 200
    assert (await db_session.execute(select(Lead).where(Lead.id == lead_id))).scalar_one_or_none() is None
    assert (await client.get("/api/v1/dashboard", headers=headers)).json()["total_revenue"] == 250


@pytest.mark.asyncio
async def test_no_followup_after_sale_or_loss(db_session):
    for i, status in enumerate((LeadStatus.CONVERTED, LeadStatus.LOST)):
        account, conv, lead, original, rule = await _setup(db_session, f"PNID_SALE{i}", phone=f"558398888100{i}")
        lead.status = status
        await db_session.flush()
        with _mock_send() as mock_send:
            assert await run_due_followups(db_session) == 0
            mock_send.assert_not_called()


@pytest.mark.asyncio
async def test_followup_waits_while_agent_owns_conversation(db_session):
    account, conv, lead, original, rule = await _setup(db_session, "PNID_SALE_AG", phone="5583988881100")
    conv.atendente_id = "agent-1"
    await db_session.flush()
    with _mock_send() as mock_send:
        assert await run_due_followups(db_session) == 0
        mock_send.assert_not_called()
    # Nada registrado: ao liberar a conversa, o follow-up volta a valer
    assert (await db_session.execute(
        select(FollowUpDispatch).where(FollowUpDispatch.account_id == account.id)
    )).scalar_one_or_none() is None

    conv.atendente_id = None
    await db_session.flush()
    with _mock_send() as mock_send:
        assert await run_due_followups(db_session) == 1
