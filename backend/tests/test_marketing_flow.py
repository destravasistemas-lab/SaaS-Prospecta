"""
Tests for the Meta Ads manager: account switching, campaign/ad set/ad CRUD,
and that budgets/targeting are translated correctly into Marketing API calls.
"""
import logging
import uuid

import pytest
from unittest.mock import AsyncMock, patch

from app.core.security import create_access_token
from app.models.account import Account
from app.models.user import User
from app.models.meta_connection import MetaConnection, PROVIDER_ADS, STATUS_ACTIVE
from app.services import ads_service
from app.services.meta_token_service import encrypt_token


async def _ads_setup(db_session):
    account = Account(brand_name="Ads Test")
    db_session.add(account)
    await db_session.flush()

    conn = MetaConnection(
        id=str(uuid.uuid4()),
        account_id=account.id,
        provider=PROVIDER_ADS,
        ad_account_id="act_111",
        page_id="PAGE_ADS_1",
        access_token_encrypted=encrypt_token("fake_ads_token"),
        status=STATUS_ACTIVE,
    )
    db_session.add(conn)

    user = User(
        id=str(uuid.uuid4()),
        tenant_id=account.id,
        username="ads_agent",
        password_hash="x",
        role="admin",
        is_active=True,
    )
    db_session.add(user)
    await db_session.flush()

    headers = {"Authorization": f"Bearer {create_access_token(user.id, account.id, 'admin')}"}
    return account, conn, headers


# ---------------------------------------------------------------------------
# Ad account listing / switching
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_list_ad_accounts(client, db_session):
    _, _, headers = await _ads_setup(db_session)

    with patch(
        "app.services.ads_service.list_ad_accounts", new_callable=AsyncMock,
        return_value=[{"id": "act_111", "name": "Conta A", "account_status": 1, "currency": "BRL"},
                      {"id": "act_222", "name": "Conta B", "account_status": 1, "currency": "BRL"}],
    ):
        resp = await client.get("/api/v1/marketing/ad-accounts", headers=headers)

    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 2
    assert data[1]["id"] == "act_222"


@pytest.mark.asyncio
async def test_switch_ad_account_persists(client, db_session):
    _, conn, headers = await _ads_setup(db_session)

    resp = await client.put(
        "/api/v1/marketing/ad-account", json={"ad_account_id": "act_222"}, headers=headers,
    )
    assert resp.status_code == 200
    await db_session.refresh(conn)
    assert conn.ad_account_id == "act_222"


# ---------------------------------------------------------------------------
# Campaign CRUD
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_create_campaign_uses_active_ad_account(client, db_session):
    _, _, headers = await _ads_setup(db_session)

    with patch(
        "app.services.ads_service.create_campaign", new_callable=AsyncMock,
        return_value={"id": "CAMP_1"},
    ) as mock_create:
        resp = await client.post(
            "/api/v1/marketing/campaigns",
            json={"name": "Campanha Teste", "objective": "OUTCOME_LEADS", "status": "PAUSED"},
            headers=headers,
        )

    assert resp.status_code == 200
    assert resp.json()["campaign_id"] == "CAMP_1"
    mock_create.assert_called_once()
    assert mock_create.call_args[0][1] == "act_111"
    assert mock_create.call_args.kwargs["is_adset_budget_sharing_enabled"] is False


@pytest.mark.parametrize("body", [
    {"name": "Nova", "objective": "OUTCOME_LEADS", "status": "PAUSED", "special_ad_categories": ["NONE"]},
    {"name": "Sem status"},
])
@pytest.mark.asyncio
async def test_new_campaign_reaches_meta_paused(client, db_session, body):
    _, _, headers = await _ads_setup(db_session)

    with patch(
        "app.services.ads_service._request", new_callable=AsyncMock, return_value={"id": "CAMP_1"},
    ) as mock_request:
        resp = await client.post("/api/v1/marketing/campaigns", json=body, headers=headers)

    assert resp.status_code == 200
    assert mock_request.call_args.kwargs["json"]["status"] == "PAUSED"


@pytest.mark.asyncio
async def test_pause_campaign(client, db_session):
    _, _, headers = await _ads_setup(db_session)

    with patch(
        "app.services.ads_service.update_campaign", new_callable=AsyncMock, return_value={"success": True},
    ) as mock_update:
        resp = await client.patch(
            "/api/v1/marketing/campaigns/CAMP_1", json={"status": "PAUSED"}, headers=headers,
        )

    assert resp.status_code == 200
    mock_update.assert_called_once_with(mock_update.call_args[0][0], "CAMP_1", status="PAUSED")


@pytest.mark.asyncio
async def test_update_ad_set_budget(client, db_session):
    _, _, headers = await _ads_setup(db_session)

    with patch(
        "app.services.ads_service.update_ad_set", new_callable=AsyncMock, return_value={"success": True},
    ) as mock_update:
        resp = await client.patch(
            "/api/v1/marketing/ad-sets/SET_1", json={"daily_budget_cents": 5000}, headers=headers,
        )
        too_low = await client.patch(
            "/api/v1/marketing/ad-sets/SET_1", json={"daily_budget_cents": 50}, headers=headers,
        )

    assert resp.status_code == 200
    mock_update.assert_called_once_with(mock_update.call_args[0][0], "SET_1", daily_budget="5000")
    assert too_low.status_code == 422


@pytest.mark.asyncio
async def test_delete_campaign(client, db_session):
    _, _, headers = await _ads_setup(db_session)

    with patch(
        "app.services.ads_service.delete_campaign", new_callable=AsyncMock, return_value={"success": True},
    ):
        resp = await client.delete("/api/v1/marketing/campaigns/CAMP_1", headers=headers)

    assert resp.status_code == 200
    assert resp.json()["success"] is True


@pytest.mark.asyncio
async def test_update_campaign_rejects_empty_body(client, db_session):
    _, _, headers = await _ads_setup(db_session)
    resp = await client.patch("/api/v1/marketing/campaigns/CAMP_1", json={}, headers=headers)
    assert resp.status_code == 422


# ---------------------------------------------------------------------------
# Ad Set creation — targeting spec translated into Graph API shape
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_create_ad_set_builds_targeting_payload(client, db_session):
    _, _, headers = await _ads_setup(db_session)

    with patch(
        "app.services.ads_service.create_ad_set", new_callable=AsyncMock,
        return_value={"id": "ADSET_1"},
    ) as mock_create:
        resp = await client.post(
            "/api/v1/marketing/ad-sets",
            json={
                "campaign_id": "CAMP_1",
                "name": "Conjunto Teste",
                "daily_budget_cents": 2000,
                "targeting": {
                    "age_min": 25, "age_max": 45, "genders": [2],
                    "country_codes": ["BR", "PT"], "interest_ids": ["6003107902433"],
                },
            },
            headers=headers,
        )

    assert resp.status_code == 200
    assert resp.json()["ad_set_id"] == "ADSET_1"
    _, kwargs = mock_create.call_args
    targeting = kwargs["targeting"]
    assert targeting["age_min"] == 25
    assert targeting["age_max"] == 45
    assert targeting["genders"] == [2]
    assert targeting["geo_locations"]["countries"] == ["BR", "PT"]
    assert targeting["flexible_spec"][0]["interests"] == [{"id": "6003107902433"}]


@pytest.mark.asyncio
async def test_create_ad_set_sends_advantage_audience_to_meta(client, db_session):
    _, _, headers = await _ads_setup(db_session)

    with patch(
        "app.services.ads_service._request", new_callable=AsyncMock, return_value={"id": "ADSET_1"},
    ) as mock_request:
        resp = await client.post(
            "/api/v1/marketing/ad-sets",
            json={
                "campaign_id": "CAMP_1",
                "name": "Conjunto Teste",
                "targeting": {"age_min": 25, "age_max": 45, "genders": [2], "interest_ids": ["6003107902433"]},
            },
            headers=headers,
        )

    assert resp.status_code == 200
    payload = mock_request.call_args.kwargs["json"]
    assert payload["status"] == "PAUSED"
    targeting = payload["targeting"]
    assert targeting["targeting_automation"] == {"advantage_audience": 0}
    assert (targeting["age_min"], targeting["age_max"], targeting["genders"]) == (25, 45, [2])
    assert targeting["flexible_spec"][0]["interests"] == [{"id": "6003107902433"}]


@pytest.mark.asyncio
async def test_create_ad_set_default_targeting_has_advantage_audience():
    with patch(
        "app.services.ads_service._request", new_callable=AsyncMock, return_value={"id": "ADSET_1"},
    ) as mock_request:
        await ads_service.create_ad_set("token", "act_111", "CAMP_1", "Conjunto", 1000)

    assert mock_request.call_args.kwargs["json"]["targeting"] == {
        "targeting_automation": {"advantage_audience": 0},
        "geo_locations": {"countries": ["BR"]},
    }


@pytest.mark.asyncio
async def test_create_ad_set_refusal_shows_message_and_logs_codes(client, db_session, caplog):
    _, _, headers = await _ads_setup(db_session)
    refusal = {"error": {
        "code": 100, "error_subcode": 1234567, "message": "Invalid parameter",
        "error_user_msg": "Mensagem da Meta para o cliente",
    }}

    with patch("app.services.ads_service._request", new_callable=AsyncMock, return_value=refusal), \
         caplog.at_level(logging.WARNING, logger="app.routes.marketing"):
        resp = await client.post(
            "/api/v1/marketing/ad-sets", json={"campaign_id": "CAMP_1", "name": "Conjunto"}, headers=headers,
        )

    assert resp.status_code == 400
    assert resp.json()["detail"] == "Mensagem da Meta para o cliente"
    assert "code=100 error_subcode=1234567" in caplog.text
    assert "fake_ads_token" not in caplog.text


@pytest.mark.asyncio
async def test_list_ad_sets_for_campaign(client, db_session):
    _, _, headers = await _ads_setup(db_session)

    with patch(
        "app.services.ads_service.list_ad_sets", new_callable=AsyncMock,
        return_value=[{"id": "ADSET_1", "name": "Conjunto 1", "status": "PAUSED"}],
    ):
        resp = await client.get("/api/v1/marketing/campaigns/CAMP_1/ad-sets", headers=headers)

    assert resp.status_code == 200
    assert resp.json()[0]["id"] == "ADSET_1"


# ---------------------------------------------------------------------------
# Creatives — video and carousel payload shape
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_create_video_creative_requires_no_image(client, db_session):
    _, _, headers = await _ads_setup(db_session)

    with patch(
        "app.services.ads_service.create_ad_creative", new_callable=AsyncMock,
        return_value={"id": "CREATIVE_1"},
    ) as mock_create:
        resp = await client.post(
            "/api/v1/marketing/creatives",
            json={
                "name": "Criativo Vídeo", "message": "Confira!",
                "video_id": "VID_123", "link_url": "https://example.com",
            },
            headers=headers,
        )

    assert resp.status_code == 200
    _, kwargs = mock_create.call_args
    assert kwargs["video_id"] == "VID_123"


@pytest.mark.asyncio
async def test_create_creative_without_page_fails(client, db_session):
    account = Account(brand_name="No Page Ads")
    db_session.add(account)
    await db_session.flush()
    conn = MetaConnection(
        id=str(uuid.uuid4()),
        account_id=account.id,
        provider=PROVIDER_ADS,
        ad_account_id="act_999",
        page_id=None,
        access_token_encrypted=encrypt_token("fake_token"),
        status=STATUS_ACTIVE,
    )
    db_session.add(conn)
    user = User(
        id=str(uuid.uuid4()), tenant_id=account.id, username="no_page_agent",
        password_hash="x", role="admin", is_active=True,
    )
    db_session.add(user)
    await db_session.flush()
    headers = {"Authorization": f"Bearer {create_access_token(user.id, account.id, 'admin')}"}

    resp = await client.post(
        "/api/v1/marketing/creatives",
        json={"name": "Criativo", "message": "Oi", "image_url": "https://example.com/a.jpg"},
        headers=headers,
    )
    assert resp.status_code == 400
