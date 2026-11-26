"""
Posts do Instagram: o agendador publica uma vez só, a mídia sai da cota ao
publicar, e mídia, fila de posts e automações têm limite por empresa.
"""
import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy import select

from app.core.config import settings
from app.models.account import Account
from app.models.automation import AutomationConfig
from app.models.billing import Plan
from app.models.meta_connection import MetaConnection, PROVIDER_INSTAGRAM, STATUS_ACTIVE
from app.models.schedule import MediaUpload, PostSchedule
from app.services import post_media, scheduler
from app.services.billing import content_limit, seed_plans
from app.services.meta_token_service import encrypt_token
from tests.conftest import TestSession


async def _ig_account(db, account_id=None):
    acc = Account(id=account_id or str(uuid.uuid4()), brand_name="Loja")
    db.add(acc)
    await db.flush()
    db.add(MetaConnection(account_id=acc.id, provider=PROVIDER_INSTAGRAM, status=STATUS_ACTIVE,
                          access_token_encrypted=encrypt_token("T"), ig_business_account_id="IG1"))
    await db.flush()
    return acc


async def _due_post(keyword=None):
    async with TestSession() as db:
        acc = await _ig_account(db)
        url = f"{post_media.local_prefix()}{uuid.uuid4().hex}.jpg"
        db.add(MediaUpload(account_id=acc.id, url=url, bytes=1000, media_type="IMAGE"))
        post = PostSchedule(account_id=acc.id, ig_user_id="IG1", media_type="IMAGE", media_url=url,
                            scheduled_for=datetime.now(timezone.utc) - timedelta(minutes=1), status="scheduled",
                            automation_keyword=keyword, automation_dm_message="Oi!" if keyword else None)
        db.add(post)
        await db.commit()
        return acc.id, post.id, url


@pytest.mark.asyncio
async def test_scheduled_post_is_published_once_and_its_media_released():
    account_id, post_id, url = await _due_post(keyword="EUQUERO")
    pub = AsyncMock(return_value={"id": f"MEDIA_{uuid.uuid4().hex[:6]}"})
    with patch.object(scheduler, "publish_image_post", pub):
        for _ in range(3):
            await scheduler.run_due_posts(TestSession)
    assert pub.await_count == 1
    async with TestSession() as db:
        post = await db.get(PostSchedule, post_id)
        assert post.status == "published" and post.published_at is not None
        upload = (await db.execute(select(MediaUpload).where(MediaUpload.url == url))).scalar_one()
        assert upload.released_at is not None
        autos = (await db.execute(select(AutomationConfig).where(AutomationConfig.account_id == account_id))).scalars().all()
        assert len(autos) == 1


@pytest.mark.asyncio
async def test_failed_publish_retries_later_then_gives_up():
    _, post_id, _ = await _due_post()
    pub = AsyncMock(side_effect=RuntimeError("Meta fora do ar"))
    with patch.object(scheduler, "publish_image_post", pub):
        await scheduler.run_due_posts(TestSession)
        await scheduler.run_due_posts(TestSession)  # ainda não venceu de novo
        assert pub.await_count == 1
        async with TestSession() as db:
            post = await db.get(PostSchedule, post_id)
            assert post.status == "scheduled" and post.retry_count == 1
            assert post.scheduled_for.replace(tzinfo=timezone.utc) > datetime.now(timezone.utc)
            for _ in range(2):
                post.scheduled_for = datetime.now(timezone.utc) - timedelta(seconds=1)
                await db.commit()
                await scheduler.run_due_posts(TestSession)
                await db.refresh(post)
    assert pub.await_count == 3 and post.status == "failed"


@pytest.mark.asyncio
async def test_post_stuck_while_publishing_is_not_republished():
    _, post_id, _ = await _due_post()
    async with TestSession() as db:
        post = await db.get(PostSchedule, post_id)
        post.status = "publishing"
        post.updated_at = datetime.now(timezone.utc) - timedelta(minutes=30)
        await db.commit()
    pub = AsyncMock(return_value={"id": "X"})
    with patch.object(scheduler, "publish_image_post", pub):
        await scheduler.run_due_posts(TestSession)
    pub.assert_not_awaited()
    async with TestSession() as db:
        post = await db.get(PostSchedule, post_id)
        assert post.status == "failed" and "Confira no Instagram" in post.error_message


@pytest.mark.asyncio
async def test_post_many_hours_late_asks_before_publishing():
    _, post_id, _ = await _due_post()
    async with TestSession() as db:
        post = await db.get(PostSchedule, post_id)
        post.scheduled_for = datetime.now(timezone.utc) - timedelta(days=2)
        await db.commit()
    pub = AsyncMock(return_value={"id": "X"})
    with patch.object(scheduler, "publish_image_post", pub):
        await scheduler.run_due_posts(TestSession)
    pub.assert_not_awaited()
    async with TestSession() as db:
        post = await db.get(PostSchedule, post_id)
        assert post.status == "failed" and "Tentar de novo" in post.error_message


@pytest.mark.asyncio
async def test_upload_counts_against_the_media_quota(client, make_user, monkeypatch, tmp_path):
    monkeypatch.setattr("app.routes.instagram_api.UPLOAD_DIR", tmp_path)
    monkeypatch.setattr(post_media, "UPLOAD_DIR", tmp_path)
    monkeypatch.setattr(settings, "default_storage_mb", 1)
    _, headers = await make_user()
    img = b"x" * (600 * 1024)
    r1 = await client.post("/api/v1/instagram/upload-media", headers=headers,
                           files={"file": ("a.jpg", img, "image/jpeg")})
    assert r1.status_code == 200, r1.text
    r2 = await client.post("/api/v1/instagram/upload-media", headers=headers,
                           files={"file": ("b.jpg", img, "image/jpeg")})
    assert r2.status_code == 413 and "1 MB" in r2.json()["detail"]
    limits = (await client.get("/api/v1/instagram/limits", headers=headers)).json()
    assert limits["storage_limit_mb"] == 1 and limits["storage_used_mb"] == 0.6


@pytest.mark.asyncio
async def test_queue_and_automation_limits(client, make_user, db_session, monkeypatch):
    monkeypatch.setattr(settings, "default_scheduled_posts", 2)
    monkeypatch.setattr(settings, "default_automations", 2)
    tid, headers = await make_user()
    db_session.add(MetaConnection(account_id=tid, provider=PROVIDER_INSTAGRAM, status=STATUS_ACTIVE,
                                  access_token_encrypted=encrypt_token("T"), ig_business_account_id="IG1"))
    await db_session.flush()
    when = (datetime.now(timezone.utc) + timedelta(days=1)).isoformat()

    def post(keyword=None):
        body = {"ig_user_id": "IG1", "media_url": "https://cdn/x.jpg", "media_type": "IMAGE", "scheduled_for": when}
        if keyword:
            body["automation_keyword"] = keyword
        return client.post("/api/v1/instagram/schedule", headers=headers, json=body)

    assert (await post("A")).status_code == 201
    assert (await post()).status_code == 201
    r = await post()
    assert r.status_code == 422 and "2 posts agendados" in r.json()["detail"]

    # 1 automação reservada pelo post da fila + 1 criada = limite
    r = await client.post("/api/v1/automations", headers=headers,
                          json={"keyword": "preço", "auto_reply_message": "Oi", "trigger_type": "dm"})
    assert r.status_code == 201, r.text
    r = await client.post("/api/v1/automations", headers=headers,
                          json={"keyword": "horário", "auto_reply_message": "Oi", "trigger_type": "dm"})
    assert r.status_code == 422 and "2 automações ativas" in r.json()["detail"]
    r = await client.post("/api/v1/automations", headers=headers,
                          json={"keyword": "endereço", "auto_reply_message": "Oi", "trigger_type": "dm", "is_active": False})
    assert r.status_code == 201
    r = await client.put(f"/api/v1/automations/{r.json()['id']}", headers=headers, json={"is_active": True})
    assert r.status_code == 422


@pytest.mark.asyncio
async def test_publish_now_twice_publishes_once(client, make_user, db_session):
    tid, headers = await make_user()
    db_session.add(MetaConnection(account_id=tid, provider=PROVIDER_INSTAGRAM, status=STATUS_ACTIVE,
                                  access_token_encrypted=encrypt_token("T"), ig_business_account_id="IG1"))
    post = PostSchedule(account_id=tid, ig_user_id="IG1", media_type="IMAGE", media_url="https://cdn/y.jpg",
                        scheduled_for=datetime.now(timezone.utc) + timedelta(hours=2), status="scheduled")
    db_session.add(post)
    await db_session.flush()
    with patch("app.routes.instagram_api.publish_image_post", new_callable=AsyncMock, return_value={"id": "M1"}) as pub:
        r1 = await client.post(f"/api/v1/instagram/schedule/{post.id}/publish-now", headers=headers)
        r2 = await client.post(f"/api/v1/instagram/schedule/{post.id}/publish-now", headers=headers)
    assert r1.status_code == 200 and r2.status_code == 409
    assert pub.await_count == 1
    r = await client.delete(f"/api/v1/instagram/schedule/{post.id}", headers=headers)
    assert r.status_code == 200


@pytest.mark.asyncio
async def test_cleanup_releases_leftovers_expires_failed_media_and_old_post_automations(db_session):
    acc = await _ig_account(db_session)
    old = datetime.now(timezone.utc) - timedelta(days=40)
    leftover = f"{post_media.local_prefix()}left.jpg"
    failed_url = f"{post_media.local_prefix()}failed.jpg"
    queued_url = f"{post_media.local_prefix()}queued.jpg"
    for url in (leftover, failed_url, queued_url):
        db_session.add(MediaUpload(account_id=acc.id, url=url, bytes=10, media_type="IMAGE", created_at=old))
    failed = PostSchedule(account_id=acc.id, ig_user_id="IG1", media_type="IMAGE", media_url=failed_url,
                          scheduled_for=old, status="failed", updated_at=old)
    queued = PostSchedule(account_id=acc.id, ig_user_id="IG1", media_type="IMAGE", media_url=queued_url,
                          scheduled_for=datetime.now(timezone.utc) + timedelta(days=1), status="scheduled")
    post_auto = AutomationConfig(account_id=acc.id, keyword="EU", auto_reply_message="Oi", trigger_type="comment",
                                 media_id="M_OLD", is_active=True, created_at=old, updated_at=old)
    general = AutomationConfig(account_id=acc.id, keyword="preço", auto_reply_message="Oi", trigger_type="dm",
                               is_active=True, created_at=old, updated_at=old)
    db_session.add_all([failed, queued, post_auto, general])
    await db_session.flush()

    await post_media.cleanup(db_session)
    await db_session.refresh(failed)
    await db_session.refresh(post_auto)
    await db_session.refresh(general)
    released = {u.url: u.released_at for u in (await db_session.execute(
        select(MediaUpload).where(MediaUpload.account_id == acc.id))).scalars().all()}
    assert released[leftover] and released[failed_url] and released[queued_url] is None
    assert failed.status == "expired"
    assert post_auto.is_active is False and general.is_active is True


@pytest.mark.asyncio
async def test_plans_get_content_limits(db_session):
    await seed_plans(db_session)
    db_session.add(Plan(code=f"velho_{uuid.uuid4().hex[:4]}", name="Velho", price_cents=1, sort=9,
                        limits={"users": 1}, modules=[], extras=[]))
    await db_session.flush()
    await seed_plans(db_session)
    plans = (await db_session.execute(select(Plan))).scalars().all()
    for p in plans:
        assert {"scheduled_posts", "storage_mb", "automations"} <= set(p.limits)
    acc = Account(id=str(uuid.uuid4()), brand_name="P", billing_plan="profissional")
    db_session.add(acc)
    await db_session.flush()
    assert await content_limit(db_session, acc.id, "storage_mb") == 1000
