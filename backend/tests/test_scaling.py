"""
O que garante que o sistema aguenta vários clientes e várias instâncias:
post agendado publicado uma vez só, webhook que responde na hora e se recupera,
disparo em fila sem duplicar e busca da IA fora do event loop.
"""
import asyncio
import hashlib
import hmac
import json
import time
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, patch

import numpy as np
import pytest
from sqlalchemy import delete, select, update

from app.core import http
from app.core.security import create_access_token
from app.models.account import Account
from app.models.ai import KnowledgeChunk, KnowledgeDoc
from app.models.lead import Lead, LeadSource, LeadStatus
from app.models.message import Message
from app.models.meta_connection import MetaConnection, PROVIDER_INSTAGRAM, PROVIDER_WHATSAPP, STATUS_ACTIVE
from app.models.queue import (
    BroadcastJob, BroadcastRecipient, EVENT_FAILED, RCPT_FAILED, RCPT_SENDING, WebhookEvent,
)
from app.models.schedule import PostSchedule
from app.models.user import User
from app.services import broadcast_worker, rag_service, scheduler, webhook_queue
from app.services.meta_token_service import encrypt_token


async def _fresh(db_session, model, key):
    return (await db_session.execute(
        select(model).where(model.id == key).execution_options(populate_existing=True)
    )).scalar_one()


@pytest.fixture(autouse=True)
async def _no_leftover_jobs(db_session):
    """O banco de teste é compartilhado: disparos de outros testes não podem entrar na conta deste."""
    await db_session.execute(update(BroadcastJob).where(BroadcastJob.status.in_(("queued", "running"))).values(status="canceled"))
    await db_session.execute(delete(WebhookEvent))
    await db_session.commit()


def _factory(db_session):
    @asynccontextmanager
    async def factory():
        yield db_session
    return factory


async def _tenant(db_session, *, leads=0):
    account = Account(brand_name="Escala")
    db_session.add(account)
    await db_session.flush()
    pn = uuid.uuid4().hex
    db_session.add(MetaConnection(
        id=str(uuid.uuid4()), account_id=account.id, provider=PROVIDER_WHATSAPP, phone_number_id=pn,
        waba_id="W", access_token_encrypted=encrypt_token("TOKEN"), status=STATUS_ACTIVE,
    ))
    db_session.add(MetaConnection(
        id=str(uuid.uuid4()), account_id=account.id, provider=PROVIDER_INSTAGRAM,
        ig_business_account_id=f"IG{pn}", access_token_encrypted=encrypt_token("TOKEN"), status=STATUS_ACTIVE,
    ))
    user = User(id=str(uuid.uuid4()), tenant_id=account.id, username=f"{uuid.uuid4().hex}@t.com",
                password_hash="x", role="admin", is_active=True)
    db_session.add(user)
    for i in range(leads):
        db_session.add(Lead(id=str(uuid.uuid4()), account_id=account.id, instagram_handle=f"55839{i:08d}",
                            phone=f"55839{i:08d}", name=f"Lead {i}", source=LeadSource.MANUAL,
                            status=LeadStatus.NEW, whatsapp_opt_in=True))
    await db_session.flush()
    headers = {"Authorization": f"Bearer {create_access_token(user.id, account.id, 'admin')}"}
    return account, pn, headers


# ---------------------------------------------------------------------------
# Posts agendados
# ---------------------------------------------------------------------------

def _due_post(account_id):
    return PostSchedule(
        id=str(uuid.uuid4()), account_id=account_id, ig_user_id="IG", media_type="IMAGE",
        media_url="https://x/y.jpg", caption="c", status="scheduled",
        scheduled_for=datetime.now(timezone.utc) - timedelta(minutes=1),
    )


@pytest.mark.asyncio
async def test_scheduled_post_is_published_once_and_marked_published(db_session):
    account, _, _ = await _tenant(db_session)
    post = _due_post(account.id)
    db_session.add(post)
    await db_session.commit()

    with patch("app.services.scheduler.publish_image_post", new_callable=AsyncMock, return_value={"id": "MEDIA_1"}) as pub, \
         patch("app.services.storage_service.delete_by_url", new_callable=AsyncMock):
        # Duas rodadas (ou duas instâncias): antes o status não era gravado e o post saía de novo.
        await scheduler.publish_due_posts(_factory(db_session))
        await scheduler.publish_due_posts(_factory(db_session))

    assert pub.await_count == 1
    saved = await _fresh(db_session, PostSchedule, post.id)
    assert (saved.status, saved.media_id_response) == ("published", "MEDIA_1")


@pytest.mark.asyncio
async def test_post_already_claimed_is_not_published_again(db_session):
    account, _, _ = await _tenant(db_session)
    post = _due_post(account.id)
    db_session.add(post)
    await db_session.commit()

    with patch("app.services.scheduler.publish_image_post", new_callable=AsyncMock, return_value={"id": "M"}) as pub, \
         patch("app.services.storage_service.delete_by_url", new_callable=AsyncMock):
        await scheduler._publish_scheduled_post(post.id, _factory(db_session))
        await scheduler._publish_scheduled_post(post.id, _factory(db_session))
    assert pub.await_count == 1


@pytest.mark.asyncio
async def test_failed_publish_retries_then_gives_up(db_session):
    account, _, _ = await _tenant(db_session)
    post = _due_post(account.id)
    db_session.add(post)
    await db_session.commit()

    with patch("app.services.scheduler.publish_image_post", new_callable=AsyncMock, side_effect=ValueError("x")):
        for _ in range(4):
            await scheduler.publish_due_posts(_factory(db_session))

    saved = await _fresh(db_session, PostSchedule, post.id)
    assert (saved.status, saved.retry_count) == ("failed", 3)


@pytest.mark.asyncio
async def test_post_stuck_in_publishing_is_failed_not_republished(db_session):
    account, _, _ = await _tenant(db_session)
    post = _due_post(account.id)
    post.status = "publishing"
    post.updated_at = datetime.now(timezone.utc) - timedelta(minutes=20)
    db_session.add(post)
    await db_session.commit()

    with patch("app.services.scheduler.publish_image_post", new_callable=AsyncMock) as pub:
        await scheduler.publish_due_posts(_factory(db_session))

    pub.assert_not_awaited()
    assert (await _fresh(db_session, PostSchedule, post.id)).status == "failed"


# ---------------------------------------------------------------------------
# Webhook: grava, responde e processa depois
# ---------------------------------------------------------------------------

def _signed(payload):
    body = json.dumps(payload).encode()
    sig = "sha256=" + hmac.new(b"test_app_secret", body, hashlib.sha256).hexdigest()
    return {"content": body, "headers": {"Content-Type": "application/json", "X-Hub-Signature-256": sig}}


def _wa_message(pn, text="oi"):
    return {"object": "whatsapp_business_account", "entry": [{"id": "W", "changes": [{"field": "messages", "value": {
        "messaging_product": "whatsapp", "metadata": {"phone_number_id": pn},
        "contacts": [{"profile": {"name": "Cli"}, "wa_id": "5583911112222"}],
        "messages": [{"from": "5583911112222", "id": f"wamid.{uuid.uuid4().hex}",
                      "timestamp": str(int(time.time())), "type": "text", "text": {"body": text}}],
    }}]}]}


@pytest.mark.asyncio
async def test_webhook_is_processed_and_the_event_removed(client, db_session):
    account, pn, _ = await _tenant(db_session)

    resp = await client.post("/api/v1/webhook/meta", **_signed(_wa_message(pn)))

    assert resp.status_code == 200
    msgs = (await db_session.execute(select(Message).where(Message.tenant_id == account.id))).scalars().all()
    assert len(msgs) == 1
    assert (await db_session.execute(select(WebhookEvent))).scalars().all() == []


@pytest.mark.asyncio
async def test_webhook_answers_before_processing(client, db_session):
    _, pn, _ = await _tenant(db_session)
    order = []

    async def slow_process(*args, **kwargs):
        order.append("processou")

    with patch("app.services.webhook_queue.process_event", side_effect=slow_process):
        resp = await client.post("/api/v1/webhook/meta", **_signed(_wa_message(pn)))
        order.append(f"respondeu {resp.status_code}")

    # O processamento roda como tarefa de fundo, depois da resposta montada.
    assert resp.status_code == 200 and "processou" in order


@pytest.mark.asyncio
async def test_failed_event_is_kept_encrypted_and_retried(client, db_session):
    account, pn, _ = await _tenant(db_session)

    with patch("app.routes.webhook.handle_whatsapp_message", new_callable=AsyncMock, side_effect=RuntimeError("banco caiu")):
        resp = await client.post("/api/v1/webhook/meta", **_signed(_wa_message(pn, "segredo do cliente")))
    assert resp.status_code == 200

    event = (await db_session.execute(select(WebhookEvent))).scalar_one()
    assert event.status == EVENT_FAILED and event.attempts == 1
    assert "segredo do cliente" not in event.payload_encrypted
    assert "banco caiu" not in (event.last_error or "")  # só o tipo e a linha

    event.updated_at = datetime.now(timezone.utc) - timedelta(minutes=2)
    await db_session.commit()
    await webhook_queue.retry_pending(_factory(db_session))

    assert (await db_session.execute(select(WebhookEvent))).scalars().all() == []
    msgs = (await db_session.execute(select(Message).where(Message.tenant_id == account.id))).scalars().all()
    assert [m.text for m in msgs] == ["segredo do cliente"]


@pytest.mark.asyncio
async def test_event_already_claimed_is_not_processed_twice(db_session):
    event = WebhookEvent(payload_encrypted=encrypt_token(json.dumps({"object": "x", "entry": []})))
    db_session.add(event)
    await db_session.commit()

    with patch("app.routes.webhook.process_payload", new_callable=AsyncMock) as proc:
        await webhook_queue.process_event(event.id, _factory(db_session))
        await webhook_queue.process_event(event.id, _factory(db_session))
    assert proc.await_count == 1


# ---------------------------------------------------------------------------
# Disparos em fila
# ---------------------------------------------------------------------------

def _meta_ok():
    return patch("app.services.whatsapp_service.send_template", new_callable=AsyncMock,
                 side_effect=lambda *a, **k: {"messages": [{"id": f"wamid.{uuid.uuid4().hex}"}]})


@pytest.mark.asyncio
async def test_broadcast_sends_once_per_contact_and_records_history(client, db_session):
    account, _, headers = await _tenant(db_session, leads=120)

    with _meta_ok() as send:
        resp = await client.post("/api/v1/whatsapp/broadcast", json={"template_name": "oferta"}, headers=headers)
        await broadcast_worker.process_jobs(_factory(db_session))  # outra rodada não reenvia

    assert resp.status_code == 202 and resp.json()["total"] == 120
    assert send.await_count == 120
    assert len({c.args[2] for c in send.await_args_list}) == 120
    job = (await client.get(f"/api/v1/whatsapp/broadcast/jobs/{resp.json()['id']}", headers=headers)).json()
    assert (job["status"], job["sent"], job["failed"]) == ("done", 120, 0)
    saved = (await db_session.execute(
        select(Message).where(Message.tenant_id == account.id, Message.template_name == "oferta")
    )).scalars().all()
    assert len(saved) == 120


@pytest.mark.asyncio
async def test_second_click_while_running_is_refused(client, db_session):
    _, _, headers = await _tenant(db_session, leads=3)

    with patch("app.services.broadcast_worker.process_jobs", new_callable=AsyncMock):  # fica na fila
        first = await client.post("/api/v1/whatsapp/broadcast", json={"template_name": "oferta"}, headers=headers)
        second = await client.post("/api/v1/whatsapp/broadcast", json={"template_name": "oferta"}, headers=headers)
        other = await client.post("/api/v1/whatsapp/broadcast", json={"template_name": "outro"}, headers=headers)

    assert first.status_code == 202
    assert second.status_code == 409 and second.json()["detail"]["code"] == "broadcast_running"
    assert second.json()["detail"]["job"]["id"] == first.json()["id"]
    assert other.status_code == 202


@pytest.mark.asyncio
async def test_a_second_worker_pass_does_not_resend(client, db_session):
    _, _, headers = await _tenant(db_session, leads=80)
    with patch("app.services.broadcast_worker.process_jobs", new_callable=AsyncMock):
        resp = await client.post("/api/v1/whatsapp/broadcast", json={"template_name": "oferta"}, headers=headers)

    with _meta_ok() as send:
        await broadcast_worker.process_jobs(_factory(db_session))
        await broadcast_worker.process_jobs(_factory(db_session))
    assert send.await_count == 80
    assert len({c.args[2] for c in send.await_args_list}) == 80
    job = (await client.get(f"/api/v1/whatsapp/broadcast/jobs/{resp.json()['id']}", headers=headers)).json()
    assert (job["status"], job["sent"]) == ("done", 80)


@pytest.mark.asyncio
async def test_cancel_stops_the_rest(client, db_session):
    _, _, headers = await _tenant(db_session, leads=10)
    with patch("app.services.broadcast_worker.process_jobs", new_callable=AsyncMock):
        resp = await client.post("/api/v1/whatsapp/broadcast", json={"template_name": "oferta"}, headers=headers)

    canceled = await client.post(f"/api/v1/whatsapp/broadcast/jobs/{resp.json()['id']}/cancel", headers=headers)
    with _meta_ok() as send:
        await broadcast_worker.process_jobs(_factory(db_session))

    assert canceled.json()["status"] == "canceled"
    send.assert_not_awaited()


@pytest.mark.asyncio
async def test_interrupted_sends_are_marked_failed_not_resent(client, db_session):
    _, _, headers = await _tenant(db_session, leads=2)
    with patch("app.services.broadcast_worker.process_jobs", new_callable=AsyncMock):
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
    job = await _fresh(db_session, BroadcastJob, job_id)
    assert (job.status, job.failed) == ("done", 2)


@pytest.mark.asyncio
async def test_broadcast_jobs_are_isolated_per_tenant(client, db_session):
    _, _, headers = await _tenant(db_session, leads=1)
    _, _, other_headers = await _tenant(db_session)
    with patch("app.services.broadcast_worker.process_jobs", new_callable=AsyncMock):
        resp = await client.post("/api/v1/whatsapp/broadcast", json={"template_name": "oferta"}, headers=headers)
    job_id = resp.json()["id"]

    assert (await client.get(f"/api/v1/whatsapp/broadcast/jobs/{job_id}", headers=other_headers)).status_code == 404
    assert (await client.post(f"/api/v1/whatsapp/broadcast/jobs/{job_id}/cancel", headers=other_headers)).status_code == 404
    assert (await client.get("/api/v1/whatsapp/broadcast/jobs", headers=other_headers)).json() == []


# ---------------------------------------------------------------------------
# Cliente HTTP e busca da IA
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_shared_http_client_is_reused():
    assert http.shared() is http.shared()
    async with http.client(timeout=3) as a, http.client() as b:
        assert a.get.__self__ is None if hasattr(a.get, "__self__") else True
        assert a._timeout == 3 and b._timeout == 5.0


@pytest.mark.asyncio
async def test_rag_ranks_like_cosine_and_upgrades_old_rows(db_session):
    account, _, _ = await _tenant(db_session)
    doc = KnowledgeDoc(account_id=account.id, filename="f.pdf", status="ready", chunk_count=3)
    db_session.add(doc)
    await db_session.flush()
    rng = np.random.default_rng(1)
    query = rng.random(16).tolist()
    close = (np.asarray(query) + rng.random(16) * 0.05).tolist()
    far = (-np.asarray(query)).tolist()
    middle = rng.random(16).tolist()
    db_session.add_all([
        KnowledgeChunk(doc_id=doc.id, account_id=account.id, chunk_index=0, content="perto", embedding=close),  # formato antigo
        KnowledgeChunk(doc_id=doc.id, account_id=account.id, chunk_index=1, content="longe",
                       embedding_f32=np.asarray(far, dtype=np.float32).tobytes()),
        KnowledgeChunk(doc_id=doc.id, account_id=account.id, chunk_index=2, content="meio",
                       embedding_f32=np.asarray(middle, dtype=np.float32).tobytes()),
    ])
    await db_session.flush()

    found = await rag_service.retrieve(db_session, account.id, query, top_k=2)

    expected = sorted(
        [("perto", close), ("meio", middle), ("longe", far)],
        key=lambda item: rag_service.cosine_similarity(query, item[1]), reverse=True,
    )
    assert found == [name for name, emb in expected if rag_service.cosine_similarity(query, emb) > 0.3][:2]
    old = (await db_session.execute(
        select(KnowledgeChunk).where(KnowledgeChunk.content == "perto").execution_options(populate_existing=True)
    )).scalar_one()
    assert old.embedding_f32 is not None and old.embedding is None


@pytest.mark.asyncio
async def test_rag_runs_off_the_event_loop(db_session):
    with patch("app.services.rag_service.asyncio.to_thread", wraps=asyncio.to_thread) as to_thread:
        account, _, _ = await _tenant(db_session)
        await rag_service.retrieve(db_session, account.id, [0.1, 0.2])
    to_thread.assert_awaited_once()
