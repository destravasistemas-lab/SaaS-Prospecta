"""
Disparo em massa em fila no Postgres: a rota cria o disparo e responde na hora,
o worker envia em lotes uma vez por contato, com as variáveis de cada lead.
"""
import json
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy import select, update

from app.core.security import create_access_token
from app.models.account import Account
from app.models.lead import Lead, LeadSource, LeadStatus
from app.models.message import Message
from app.models.meta_connection import MetaConnection, PROVIDER_WHATSAPP, STATUS_ACTIVE
from app.models.queue import JOB_ACTIVE, RCPT_FAILED, RCPT_SENDING, RCPT_SKIPPED, BroadcastJob, BroadcastRecipient
from app.models.user import User
from app.services import broadcast_worker
from app.services.meta_token_service import encrypt_token


@pytest.fixture(autouse=True)
async def _no_leftover_jobs(db_session):
    """O banco de teste é compartilhado: disparo parado na fila não pode vazar para outro teste."""
    await db_session.execute(update(BroadcastJob).where(BroadcastJob.status.in_(JOB_ACTIVE)).values(status="canceled"))
    await db_session.commit()
    yield
    await db_session.execute(update(BroadcastJob).where(BroadcastJob.status.in_(JOB_ACTIVE)).values(status="canceled"))
    await db_session.commit()


def _factory(db_session):
    @asynccontextmanager
    async def factory():
        yield db_session
    return factory


async def _tenant(db_session, *, leads=0, **lead_kw):
    account = Account(brand_name="Fila")
    db_session.add(account)
    await db_session.flush()
    db_session.add(MetaConnection(
        id=str(uuid.uuid4()), account_id=account.id, provider=PROVIDER_WHATSAPP, phone_number_id=uuid.uuid4().hex,
        waba_id="W", access_token_encrypted=encrypt_token("TOKEN"), status=STATUS_ACTIVE,
    ))
    user = User(id=str(uuid.uuid4()), tenant_id=account.id, username=f"{uuid.uuid4().hex}@t.com",
                password_hash="x", role="admin", is_active=True)
    db_session.add(user)
    for i in range(leads):
        db_session.add(_lead(account.id, f"55839{i:08d}", f"Cliente {i}", **lead_kw))
    await db_session.flush()
    headers = {"Authorization": f"Bearer {create_access_token(user.id, account.id, 'admin')}"}
    return account, headers


def _lead(account_id, phone, name, **kw):
    return Lead(id=str(uuid.uuid4()), account_id=account_id, phone=phone, name=name, source=LeadSource.MANUAL,
                status=LeadStatus.NEW, whatsapp_opt_in=kw.pop("whatsapp_opt_in", True),
                instagram_handle=f"{phone}-{uuid.uuid4().hex[:6]}", **kw)


def _meta_ok():
    return patch("app.services.whatsapp_service.send_template", new_callable=AsyncMock,
                 side_effect=lambda *a, **k: {"messages": [{"id": f"wamid.{uuid.uuid4().hex}"}]})


def _hold():
    """Deixa o disparo na fila (o worker não roda na hora)."""
    return patch("app.services.broadcast_worker.process_jobs", new_callable=AsyncMock)


async def _job(client, headers, job_id):
    return (await client.get(f"/api/v1/whatsapp/broadcast/jobs/{job_id}", headers=headers)).json()


@pytest.mark.asyncio
async def test_broadcast_sends_once_per_contact_and_records_history(client, db_session):
    account, headers = await _tenant(db_session, leads=120)
    with _meta_ok() as send:
        resp = await client.post("/api/v1/whatsapp/broadcast", json={"template_name": "oferta"}, headers=headers)
        await broadcast_worker.process_jobs(_factory(db_session))  # outra rodada não reenvia

    assert resp.status_code == 202 and resp.json()["total"] == 120
    assert send.await_count == 120
    assert len({c.args[2] for c in send.await_args_list}) == 120
    job = await _job(client, headers, resp.json()["id"])
    assert (job["status"], job["sent"], job["failed"], job["skipped"]) == ("done", 120, 0, 0)
    saved = (await db_session.execute(
        select(Message).where(Message.tenant_id == account.id, Message.template_name == "oferta")
    )).scalars().all()
    assert len(saved) == 120


@pytest.mark.asyncio
async def test_each_contact_gets_its_own_variables_and_empty_fields_are_skipped(client, db_session):
    account, headers = await _tenant(db_session)
    db_session.add_all([
        _lead(account.id, "5583900000001", "Maria Souza", metadata_json=json.dumps({"campos": {"cidade": "Recife"}})),
        _lead(account.id, "5583900000002", "João", metadata_json=json.dumps({"campos": {}})),
    ])
    await db_session.flush()
    body = {"template_name": "promo", "variables": ["{{primeiro_nome}}", "{{cidade}}"]}
    with _meta_ok() as send:
        resp = await client.post("/api/v1/whatsapp/broadcast", json=body, headers=headers)

    assert send.await_count == 1
    args = send.await_args_list[0].args
    assert args[2] == "5583900000001"
    assert [p["text"] for p in args[5][0]["parameters"]] == ["Maria", "Recife"]
    job = await _job(client, headers, resp.json()["id"])
    assert (job["sent"], job["skipped"]) == (1, 1)
    skipped = (await db_session.execute(
        select(BroadcastRecipient).where(BroadcastRecipient.job_id == job["id"], BroadcastRecipient.status == RCPT_SKIPPED)
    )).scalar_one()
    assert skipped.error == "Campo vazio: cidade"
    msg = (await db_session.execute(
        select(Message).where(Message.tenant_id == account.id, Message.template_name == "promo")
    )).scalar_one()
    assert msg.template_vars == {"variables": ["Maria", "Recife"]}


@pytest.mark.asyncio
async def test_blank_variable_is_refused(client, db_session):
    _, headers = await _tenant(db_session, leads=1)
    resp = await client.post("/api/v1/whatsapp/broadcast", json={"template_name": "promo", "variables": ["Oi", " "]},
                             headers=headers)
    assert resp.status_code == 422 and "{{2}}" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_same_phone_twice_and_late_opt_out(client, db_session):
    account, headers = await _tenant(db_session)
    first = _lead(account.id, "5583911110000", "Ana")
    dup = _lead(account.id, "5583911110000", "Ana (duplicada)")
    later_out = _lead(account.id, "5583922220000", "Bia")
    no_opt_in = _lead(account.id, "5583933330000", "Caio", whatsapp_opt_in=False)
    db_session.add_all([first, dup, later_out, no_opt_in])
    await db_session.flush()
    with _hold():
        resp = await client.post("/api/v1/whatsapp/broadcast",
                                 json={"template_name": "aviso", "include_without_opt_in": True}, headers=headers)
    assert resp.json()["total"] == 3  # o número repetido entra uma vez

    later_out.whatsapp_opted_out_at = datetime.now(timezone.utc)
    await db_session.flush()
    with _meta_ok() as send:
        await broadcast_worker.process_jobs(_factory(db_session))
    assert sorted(c.args[2] for c in send.await_args_list) == ["5583911110000", "5583933330000"]
    job = await _job(client, headers, resp.json()["id"])
    assert (job["sent"], job["skipped"]) == (2, 1)
    marked = (await db_session.execute(
        select(Message).where(Message.tenant_id == account.id, Message.wa_id == "5583933330000")
    )).scalar_one()
    assert marked.payload == {"sent_without_opt_in": True}


@pytest.mark.asyncio
async def test_second_click_while_running_is_refused(client, db_session):
    _, headers = await _tenant(db_session, leads=3)
    with _hold():
        first = await client.post("/api/v1/whatsapp/broadcast", json={"template_name": "oferta"}, headers=headers)
        second = await client.post("/api/v1/whatsapp/broadcast", json={"template_name": "oferta"}, headers=headers)
        other = await client.post("/api/v1/whatsapp/broadcast", json={"template_name": "outro"}, headers=headers)
    assert first.status_code == 202
    assert second.status_code == 409 and second.json()["detail"]["code"] == "broadcast_running"
    assert second.json()["detail"]["job"]["id"] == first.json()["id"]
    assert other.status_code == 202


@pytest.mark.asyncio
async def test_a_second_worker_pass_does_not_resend(client, db_session):
    _, headers = await _tenant(db_session, leads=80)
    with _hold():
        resp = await client.post("/api/v1/whatsapp/broadcast", json={"template_name": "oferta"}, headers=headers)
    with _meta_ok() as send:
        await broadcast_worker.process_jobs(_factory(db_session))
        await broadcast_worker.process_jobs(_factory(db_session))
    assert send.await_count == 80
    assert len({c.args[2] for c in send.await_args_list}) == 80
    job = await _job(client, headers, resp.json()["id"])
    assert (job["status"], job["sent"]) == ("done", 80)


@pytest.mark.asyncio
async def test_cancel_stops_the_rest(client, db_session):
    _, headers = await _tenant(db_session, leads=10)
    with _hold():
        resp = await client.post("/api/v1/whatsapp/broadcast", json={"template_name": "oferta"}, headers=headers)
    canceled = await client.post(f"/api/v1/whatsapp/broadcast/jobs/{resp.json()['id']}/cancel", headers=headers)
    with _meta_ok() as send:
        await broadcast_worker.process_jobs(_factory(db_session))
    assert canceled.json()["status"] == "canceled"
    send.assert_not_awaited()


@pytest.mark.asyncio
async def test_interrupted_sends_are_marked_failed_not_resent(client, db_session):
    _, headers = await _tenant(db_session, leads=2)
    with _hold():
        resp = await client.post("/api/v1/whatsapp/broadcast", json={"template_name": "oferta"}, headers=headers)
    job_id = resp.json()["id"]
    await db_session.execute(
        update(BroadcastRecipient).where(BroadcastRecipient.job_id == job_id)
        .values(status=RCPT_SENDING, updated_at=datetime.now(timezone.utc) - timedelta(minutes=10))
    )
    await db_session.commit()

    await broadcast_worker.recover_interrupted(_factory(db_session))
    with _meta_ok() as send:
        await broadcast_worker.process_jobs(_factory(db_session))
    send.assert_not_awaited()
    rows = (await db_session.execute(
        select(BroadcastRecipient.status).where(BroadcastRecipient.job_id == job_id)
    )).scalars().all()
    assert rows == [RCPT_FAILED, RCPT_FAILED]
    job = await _job(client, headers, job_id)
    assert (job["status"], job["failed"]) == ("done", 2)


@pytest.mark.asyncio
async def test_account_error_stops_the_whole_broadcast(client, db_session):
    _, headers = await _tenant(db_session, leads=5)
    refused = {"error": {"code": 132001, "message": "Template name does not exist in the translation"}}
    with patch("app.services.whatsapp_service.send_template", new_callable=AsyncMock, return_value=refused):
        resp = await client.post("/api/v1/whatsapp/broadcast", json={"template_name": "sumiu"}, headers=headers)
    job = await _job(client, headers, resp.json()["id"])
    assert job["status"] == "failed" and job["sent"] == 0 and job["error_code"] == 132001


@pytest.mark.asyncio
async def test_broadcast_jobs_are_isolated_per_tenant(client, db_session):
    _, headers = await _tenant(db_session, leads=1)
    _, other_headers = await _tenant(db_session)
    with _hold():
        resp = await client.post("/api/v1/whatsapp/broadcast", json={"template_name": "oferta"}, headers=headers)
    job_id = resp.json()["id"]
    assert (await client.get(f"/api/v1/whatsapp/broadcast/jobs/{job_id}", headers=other_headers)).status_code == 404
    assert (await client.post(f"/api/v1/whatsapp/broadcast/jobs/{job_id}/cancel", headers=other_headers)).status_code == 404
    assert (await client.get("/api/v1/whatsapp/broadcast/jobs", headers=other_headers)).json() == []
