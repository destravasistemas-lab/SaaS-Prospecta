"""Manual lead creation."""
import pytest
from sqlalchemy import select

from app.models.lead import Lead


@pytest.mark.asyncio
async def test_create_lead_with_phone_and_opt_in(client, db_session, make_user):
    tid, headers = await make_user()
    resp = await client.post("/api/v1/leads", json={
        "name": "Maria Souza", "phone": "(83) 99999-8888", "email": "Maria@Ex.com",
        "instagram_username": "@maria", "whatsapp_opt_in": True, "notes": "Veio da feira",
    }, headers=headers)
    assert resp.status_code == 201
    data = resp.json()
    assert data["phone"] == "5583999998888"
    assert data["instagram_handle"] == "5583999998888"  # WhatsApp messages from this number match this lead
    assert data["email"] == "maria@ex.com"
    assert data["source"] == "manual"
    assert data["whatsapp_opt_in"] is True
    assert data["score"] is not None

    lead = (await db_session.execute(select(Lead).where(Lead.id == data["id"]))).scalar_one()
    assert lead.account_id == tid and "maria" in lead.metadata_json


@pytest.mark.asyncio
async def test_create_lead_rejects_duplicates_and_empty_contact(client, make_user):
    _, headers = await make_user()
    first = await client.post("/api/v1/leads", json={"name": "A", "phone": "83 98888-7777"}, headers=headers)
    assert first.status_code == 201

    dup = await client.post("/api/v1/leads", json={"name": "B", "phone": "+55 83 98888-7777"}, headers=headers)
    assert dup.status_code == 409
    assert dup.json()["detail"]["code"] == "duplicate"
    assert dup.json()["detail"]["lead_id"] == first.json()["id"]

    empty = await client.post("/api/v1/leads", json={"name": "C"}, headers=headers)
    assert empty.status_code == 422

    bad_phone = await client.post("/api/v1/leads", json={"name": "D", "phone": "123"}, headers=headers)
    assert bad_phone.status_code == 422


@pytest.mark.asyncio
async def test_opt_in_ignored_without_phone(client, make_user):
    _, headers = await make_user()
    resp = await client.post("/api/v1/leads", json={
        "name": "Só Insta", "instagram_username": "joao", "whatsapp_opt_in": True,
    }, headers=headers)
    assert resp.status_code == 201
    assert resp.json()["instagram_handle"] == "@joao"
    assert resp.json()["whatsapp_opt_in"] is False
