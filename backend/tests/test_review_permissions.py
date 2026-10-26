"""
Features each App Review permission is demonstrated with: business portfolios
(business_management), Page list (pages_show_list), Page webhooks
(pages_manage_metadata), Page posts (pages_read_engagement), boosting a Page
post (pages_manage_ads) and Instagram comment moderation
(instagram_business_manage_comments).
"""
import uuid
from unittest.mock import AsyncMock, patch

import pytest

from app.core.security import create_access_token
from app.models.user import User
from app.models.meta_connection import MetaConnection

from tests.test_marketing_flow import _ads_setup
from tests.test_instagram_flow import _ig_tenant

PAGES = [
    {"id": "111", "name": "Loja A", "category": "Shopping", "picture": {"data": {"url": "https://x/a.jpg"}},
     "tasks": ["ADVERTISE", "MANAGE"], "access_token": "PAGE_TOKEN_A"},
    {"id": "222", "name": "Loja B", "category": "Shopping", "tasks": ["ADVERTISE"], "access_token": "PAGE_TOKEN_B"},
]


# ---------------------------------------------------------------------------
# business_management
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_businesses_group_owned_and_client_ad_accounts(client, db_session):
    _, _, headers = await _ads_setup(db_session)
    businesses = [{
        "id": "BM1", "name": "Agência X",
        "owned_ad_accounts": {"data": [{"id": "act_1", "name": "Própria", "account_status": 1, "currency": "BRL"}]},
        "client_ad_accounts": {"data": [
            {"id": "act_2", "name": "Cliente", "account_status": 1, "currency": "USD"},
            {"id": "act_1", "name": "Própria", "account_status": 1, "currency": "BRL"},
        ]},
    }]
    with patch("app.services.ads_service.list_businesses", new_callable=AsyncMock, return_value=businesses):
        resp = await client.get("/api/v1/marketing/businesses", headers=headers)
    assert resp.status_code == 200
    [bm] = resp.json()
    assert bm["name"] == "Agência X"
    assert [(a["id"], a["relationship"]) for a in bm["ad_accounts"]] == [("act_1", "owned"), ("act_2", "client")]
    assert bm["ad_accounts"][1]["business_name"] == "Agência X"


# ---------------------------------------------------------------------------
# pages_show_list / pages_manage_metadata
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_list_pages_marks_selected(client, db_session):
    _, conn, headers = await _ads_setup(db_session)
    conn.page_id = "222"
    await db_session.flush()
    with patch("app.services.ads_service.list_pages", new_callable=AsyncMock, return_value=PAGES):
        resp = await client.get("/api/v1/marketing/pages", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert [(p["id"], p["selected"]) for p in data] == [("111", False), ("222", True)]
    assert data[0]["picture_url"] == "https://x/a.jpg"
    assert "access_token" not in data[0]


@pytest.mark.asyncio
async def test_select_page_saves_and_subscribes_with_page_token(client, db_session):
    _, conn, headers = await _ads_setup(db_session)
    with patch("app.services.ads_service.list_pages", new_callable=AsyncMock, return_value=PAGES), \
         patch("app.services.ads_service.subscribe_page", new_callable=AsyncMock,
               return_value={"success": True}) as sub:
        resp = await client.put("/api/v1/marketing/page", json={"page_id": "111"}, headers=headers)
    assert resp.status_code == 200
    assert resp.json()["leadgen_subscribed"] is True
    sub.assert_awaited_once_with("PAGE_TOKEN_A", "111")
    await db_session.refresh(conn)
    assert conn.page_id == "111"


@pytest.mark.asyncio
async def test_select_page_rejects_page_user_does_not_manage(client, db_session):
    _, conn, headers = await _ads_setup(db_session)
    with patch("app.services.ads_service.list_pages", new_callable=AsyncMock, return_value=PAGES), \
         patch("app.services.ads_service.subscribe_page", new_callable=AsyncMock) as sub:
        resp = await client.put("/api/v1/marketing/page", json={"page_id": "999"}, headers=headers)
    assert resp.status_code == 404
    sub.assert_not_awaited()
    await db_session.refresh(conn)
    assert conn.page_id == "PAGE_ADS_1"


@pytest.mark.asyncio
async def test_page_webhook_status_subscribe_and_unsubscribe(client, db_session):
    _, _, headers = await _ads_setup(db_session)
    with patch("app.services.ads_service.list_pages", new_callable=AsyncMock, return_value=PAGES), \
         patch("app.services.ads_service.get_page_subscribed_fields", new_callable=AsyncMock,
               return_value=["leadgen"]):
        status = await client.get("/api/v1/marketing/pages/111/webhooks", headers=headers)
    assert status.json() == {"page_id": "111", "subscribed": True, "fields": ["leadgen"]}

    with patch("app.services.ads_service.list_pages", new_callable=AsyncMock, return_value=PAGES), \
         patch("app.services.ads_service.unsubscribe_page", new_callable=AsyncMock, return_value={"success": True}):
        off = await client.delete("/api/v1/marketing/pages/111/webhooks", headers=headers)
    assert off.json()["subscribed"] is False

    with patch("app.services.ads_service.list_pages", new_callable=AsyncMock, return_value=PAGES), \
         patch("app.services.ads_service.subscribe_page", new_callable=AsyncMock,
               return_value={"error": {"message": "(#200) Requires pages_manage_metadata"}}):
        bad = await client.post("/api/v1/marketing/pages/111/webhooks", headers=headers)
    assert bad.status_code == 400
    assert "pages_manage_metadata" in bad.json()["detail"]


# ---------------------------------------------------------------------------
# pages_read_engagement / pages_manage_ads
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_page_posts_use_selected_page_token(client, db_session):
    _, conn, headers = await _ads_setup(db_session)
    conn.page_id = "111"
    await db_session.flush()
    posts = [{"id": "111_9", "message": "Promo de verão", "full_picture": "https://x/p.jpg",
              "permalink_url": "https://facebook.com/111_9", "created_time": "2026-10-01T10:00:00+0000"}]
    with patch("app.services.ads_service.list_pages", new_callable=AsyncMock, return_value=PAGES), \
         patch("app.services.ads_service.list_page_posts", new_callable=AsyncMock, return_value=posts) as lp:
        resp = await client.get("/api/v1/marketing/page-posts", headers=headers)
    assert resp.status_code == 200
    assert resp.json()[0] == {"id": "111_9", "message": "Promo de verão", "picture_url": "https://x/p.jpg",
                              "permalink": "https://facebook.com/111_9", "created_time": "2026-10-01T10:00:00+0000"}
    lp.assert_awaited_once_with("PAGE_TOKEN_A", "111")


@pytest.mark.asyncio
async def test_creative_from_page_post_uses_object_story_id(client, db_session):
    _, _, headers = await _ads_setup(db_session)
    with patch("app.services.ads_service.create_creative_from_page_post", new_callable=AsyncMock,
               return_value={"id": "CR_1"}) as cc:
        resp = await client.post("/api/v1/marketing/creatives",
                                 json={"name": "Boost", "source_page_post_id": "111_9"}, headers=headers)
    assert resp.status_code == 200 and resp.json()["creative_id"] == "CR_1"
    cc.assert_awaited_once_with("fake_ads_token", "act_111", "Boost", "111_9")

    bad = await client.post("/api/v1/marketing/creatives",
                            json={"name": "Boost", "source_page_post_id": "not-a-post"}, headers=headers)
    assert bad.status_code == 422


# ---------------------------------------------------------------------------
# instagram_business_manage_comments
# ---------------------------------------------------------------------------

async def _ig_admin(db_session, ig_id: str):
    account, conn = await _ig_tenant(db_session, ig_id)
    user = User(id=str(uuid.uuid4()), tenant_id=account.id, username=f"{uuid.uuid4()}@t.com",
                password_hash="x", role="admin", is_active=True)
    db_session.add(user)
    await db_session.flush()
    return {"Authorization": f"Bearer {create_access_token(user.id, account.id, 'admin')}"}


@pytest.mark.asyncio
async def test_list_comments_flattens_replies(client, db_session):
    headers = await _ig_admin(db_session, "IG_MOD_1")
    raw = [{"id": "C1", "text": "Quanto custa?", "username": "ana", "timestamp": "2026-10-01T10:00:00+0000",
            "hidden": False, "like_count": 2,
            "replies": {"data": [{"id": "R1", "text": "Chamei no direct!", "username": "loja", "hidden": False}]}}]
    with patch("app.services.instagram_service.list_comments", new_callable=AsyncMock, return_value=raw) as lc:
        resp = await client.get("/api/v1/instagram/media/M1/comments", headers=headers)
    assert resp.status_code == 200
    [c] = resp.json()
    assert c["id"] == "C1" and c["hidden"] is False and c["replies"][0]["id"] == "R1"
    lc.assert_awaited_once_with("fake_ig_token", "M1")


@pytest.mark.asyncio
async def test_comment_create_reply_hide_delete(client, db_session):
    headers = await _ig_admin(db_session, "IG_MOD_2")
    with patch("app.services.instagram_service.create_comment", new_callable=AsyncMock, return_value={"id": "C9"}):
        created = await client.post("/api/v1/instagram/media/M1/comments", json={"message": "Novidade!"}, headers=headers)
    assert created.status_code == 201 and created.json()["id"] == "C9"

    with patch("app.services.instagram_service.reply_to_comment", new_callable=AsyncMock, return_value={"id": "R9"}) as rp:
        replied = await client.post("/api/v1/instagram/comments/C1/replies", json={"message": "Obrigado!"}, headers=headers)
    assert replied.status_code == 201
    rp.assert_awaited_once_with("fake_ig_token", "C1", "Obrigado!")

    with patch("app.services.instagram_service.set_comment_hidden", new_callable=AsyncMock,
               return_value={"success": True}) as hd:
        hidden = await client.post("/api/v1/instagram/comments/C1/visibility", json={"hide": True}, headers=headers)
    assert hidden.json() == {"id": "C1", "hidden": True}
    hd.assert_awaited_once_with("fake_ig_token", "C1", True)

    with patch("app.services.instagram_service.delete_comment", new_callable=AsyncMock, return_value={"success": True}):
        deleted = await client.delete("/api/v1/instagram/comments/C1", headers=headers)
    assert deleted.status_code == 204


@pytest.mark.asyncio
async def test_comment_graph_error_surfaces_and_auth_required(client, db_session):
    headers = await _ig_admin(db_session, "IG_MOD_3")
    with patch("app.services.instagram_service.delete_comment", new_callable=AsyncMock,
               return_value={"error": {"message": "Unsupported delete request"}}):
        resp = await client.delete("/api/v1/instagram/comments/C1", headers=headers)
    assert resp.status_code == 502
    assert "Unsupported delete request" in resp.json()["detail"]

    assert (await client.get("/api/v1/instagram/media/M1/comments")).status_code == 401
