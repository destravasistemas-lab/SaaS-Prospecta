"""
Sync periódico da Marketing API e perfil de quem comentou no Instagram.
"""
import logging
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, patch

import httpx
import pytest
import pytest_asyncio
from sqlalchemy import delete, select

from app import main as app_main
from app.core.database import Base
from app.main import app, lifespan
from app.models.account import Account
from app.models.ads_sync import AdsSyncSnapshot
from app.models.meta_connection import (
    MetaConnection, PROVIDER_ADS, STATUS_ACTIVE, STATUS_NEEDS_REAUTH, STATUS_REVOKED,
)
from app.routes.privacy import purge_meta_user_data
from app.routes.webhook import _build_person_context
from app.services import ads_sync, instagram_service
from app.services.meta_token_service import encrypt_token

TOKEN = "SYNC_TOKEN_SECRET"
_RealAsyncClient = httpx.AsyncClient


def _graph(overrides: dict | None = None, seen: list | None = None):
    """Graph falsa. overrides: seção → (status, corpo)."""
    overrides = overrides or {}
    calls = [] if seen is None else seen

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "GET"
        section = request.url.path.rsplit("/", 1)[-1]
        if section == "adsets":
            section = "ad_sets"
        if section == "insights":
            section = f"insights_{request.url.params['breakdowns']}"
        calls.append((request.url.path.split("/")[2], section))
        status, body = overrides.get(section, (200, {"data": [{"id": section}]}))
        return httpx.Response(status, json=body) if isinstance(body, dict) else httpx.Response(status, text=body)

    return handler, calls


def _use(handler):
    return patch.object(
        ads_sync.httpx, "AsyncClient",
        lambda **kw: _RealAsyncClient(transport=httpx.MockTransport(handler), **kw),
    )


@pytest_asyncio.fixture
async def sync_db(db_session):
    @asynccontextmanager
    async def _factory():
        yield db_session

    with patch.object(ads_sync, "async_session", _factory):
        yield db_session
    await db_session.rollback()
    await db_session.execute(delete(AdsSyncSnapshot))
    await db_session.execute(delete(MetaConnection))
    await db_session.commit()


async def _connect(db, ad_account="act_1", status=STATUS_ACTIVE, expires_at=None, tenant_id=None):
    tenant_id = tenant_id or str(uuid.uuid4())
    if not await db.get(Account, tenant_id):
        db.add(Account(id=tenant_id, brand_name="Ads"))
    conn = MetaConnection(
        id=str(uuid.uuid4()), account_id=tenant_id, provider=PROVIDER_ADS, ad_account_id=ad_account,
        meta_user_id=f"user-{tenant_id}", access_token_encrypted=encrypt_token(TOKEN),
        status=status, expires_at=expires_at,
    )
    db.add(conn)
    await db.flush()
    return conn


@pytest.mark.asyncio
async def test_round_saves_all_sections_with_gets_only_and_hides_token(sync_db, caplog):
    conn = await _connect(sync_db)
    handler, calls = _graph()
    with _use(handler), caplog.at_level(logging.INFO):
        await ads_sync.run_ads_sync_round()

    assert [section for _, section in calls] == [
        "campaigns", "ad_sets", "ads", "insights_age", "insights_gender", "insights_publisher_platform",
    ]
    snapshot = await sync_db.get(AdsSyncSnapshot, conn.account_id)
    assert snapshot.ad_account_id == "act_1"
    assert set(snapshot.data) == {section for _, section in calls}
    assert snapshot.synced_at is not None
    assert "ads_sync: 6 chamadas, 6 ok" in caplog.text
    assert TOKEN not in caplog.text
    assert "access_token=***" in caplog.text


@pytest.mark.asyncio
async def test_follows_pagination(sync_db, caplog):
    conn = await _connect(sync_db)
    pages = [
        {"data": [{"id": "c1"}], "paging": {"next": f"https://graph.facebook.com/v21.0/act_1/campaigns?access_token={TOKEN}&after=x"}},
        {"data": [{"id": "c2"}]},
    ]
    calls = []

    def handler(request):
        section = request.url.path.rsplit("/", 1)[-1]
        calls.append(section)
        return httpx.Response(200, json=pages.pop(0) if section == "campaigns" else {"data": []})

    with _use(handler), caplog.at_level(logging.INFO):
        await ads_sync.run_ads_sync_round()

    snapshot = await sync_db.get(AdsSyncSnapshot, conn.account_id)
    assert [c["id"] for c in snapshot.data["campaigns"]] == ["c1", "c2"]
    assert "ads_sync: 7 chamadas, 7 ok" in caplog.text
    assert TOKEN not in caplog.text


@pytest.mark.parametrize("code", [4, 17, 613, 80000, 80004, 80014])
@pytest.mark.asyncio
async def test_rate_limit_ends_the_round_without_retry(sync_db, caplog, code):
    first = await _connect(sync_db, "act_1")
    second = await _connect(sync_db, "act_2")
    handler, calls = _graph({"ad_sets": (400, {"error": {"code": code, "message": "limit"}})})
    with _use(handler), caplog.at_level(logging.INFO):
        await ads_sync.run_ads_sync_round()

    assert len(calls) == 2
    assert len({account for account, _ in calls}) == 1
    assert "ads_sync: 2 chamadas, 1 ok" in caplog.text
    snapshots = {s.account_id: s for s in (await sync_db.execute(select(AdsSyncSnapshot))).scalars()}
    assert len(snapshots) == 1
    limited_id = next(iter(snapshots))
    assert limited_id in (first.account_id, second.account_id)
    assert not snapshots[limited_id].cooldowns

    # A próxima rodada começa por quem ficou de fora
    calls.clear()
    with _use(handler):
        await ads_sync.run_ads_sync_round()
    assert calls[0][0] != ("act_1" if limited_id == first.account_id else "act_2")


@pytest.mark.asyncio
async def test_http_429_ends_the_round(sync_db, caplog):
    await _connect(sync_db)
    handler, calls = _graph({"campaigns": (429, {})})
    with _use(handler), caplog.at_level(logging.INFO):
        await ads_sync.run_ads_sync_round()
    assert len(calls) == 1
    assert "ads_sync: 1 chamadas, 0 ok" in caplog.text


@pytest.mark.asyncio
async def test_failed_section_waits_for_the_cooldown(sync_db, caplog):
    conn = await _connect(sync_db)
    handler, calls = _graph({"insights_age": (400, {"error": {"code": 100, "message": "bad"}})})
    with _use(handler), caplog.at_level(logging.INFO):
        await ads_sync.run_ads_sync_round()
    assert len(calls) == 4
    assert "ads_sync: 4 chamadas, 3 ok" in caplog.text

    calls.clear()
    with _use(handler):
        await ads_sync.run_ads_sync_round()
    assert "insights_age" not in [section for _, section in calls]
    assert "insights_gender" in [section for _, section in calls]

    snapshot = await sync_db.get(AdsSyncSnapshot, conn.account_id)
    past = (datetime.now(timezone.utc) - timedelta(minutes=1)).isoformat()
    snapshot.cooldowns = {"insights_age": past}
    await sync_db.commit()
    calls.clear()
    with _use(handler):
        await ads_sync.run_ads_sync_round()
    assert "insights_age" in [section for _, section in calls]


@pytest.mark.asyncio
async def test_server_error_is_not_retried(sync_db, caplog):
    await _connect(sync_db)
    handler, calls = _graph({"campaigns": (500, "Internal Server Error")})
    with _use(handler), caplog.at_level(logging.INFO), \
            patch("asyncio.sleep", AsyncMock()) as sleep:
        await ads_sync.run_ads_sync_round()
    assert len(calls) == 1
    sleep.assert_not_awaited()
    assert "ads_sync: 1 chamadas, 0 ok" in caplog.text


@pytest.mark.asyncio
async def test_invalid_token_asks_for_reconnection_and_stops_calling(sync_db):
    conn = await _connect(sync_db)
    handler, calls = _graph({"campaigns": (400, {"error": {"code": 190, "message": "expired"}})})
    with _use(handler):
        await ads_sync.run_ads_sync_round()
        await ads_sync.run_ads_sync_round()
    assert len(calls) == 1
    assert conn.status == STATUS_NEEDS_REAUTH


@pytest.mark.asyncio
async def test_expired_token_makes_no_call(sync_db):
    conn = await _connect(sync_db, expires_at=datetime.now(timezone.utc) - timedelta(days=1))
    handler, calls = _graph()
    with _use(handler):
        await ads_sync.run_ads_sync_round()
    assert calls == []
    assert conn.status == STATUS_NEEDS_REAUTH


@pytest.mark.asyncio
async def test_only_active_connections_are_synced(sync_db):
    await _connect(sync_db, status=STATUS_REVOKED)
    await _connect(sync_db, ad_account=None)
    handler, calls = _graph()
    with _use(handler):
        await ads_sync.run_ads_sync_round()
    assert calls == []


@pytest.mark.asyncio
async def test_disconnect_during_the_round_discards_what_was_read(sync_db):
    conn = await _connect(sync_db)
    target = (await ads_sync._load_targets())[0]
    conn.status = STATUS_REVOKED
    await ads_sync._save(target, {"campaigns": [{"id": "c1"}]}, {})
    assert await sync_db.get(AdsSyncSnapshot, conn.account_id) is None


@pytest.mark.asyncio
async def test_overview_reads_the_snapshot_without_calling_meta(client, sync_db, make_user):
    tenant_id, headers = await make_user()
    conn = await _connect(sync_db, tenant_id=tenant_id)

    empty = await client.get("/api/v1/marketing/synced-overview", headers=headers)
    assert empty.status_code == 200
    assert empty.json() == {"synced_at": None, "campaign_counts": {}, "breakdowns": {}}

    sync_db.add(AdsSyncSnapshot(
        account_id=tenant_id, ad_account_id="act_1", synced_at=datetime.now(timezone.utc),
        data={
            "campaigns": [{"id": "c1"}],
            "ad_sets": [{"id": "s1", "campaign_id": "c1"}, {"id": "s2", "campaign_id": "c1"}],
            "ads": [{"id": "a1", "campaign_id": "c1"}, {"id": "a2", "campaign_id": "other"}],
            "insights_age": [{"age": "25-34", "spend": "12.5", "impressions": "100", "clicks": "3"}],
        },
    ))
    await sync_db.flush()

    with patch.object(ads_sync.httpx, "AsyncClient", side_effect=AssertionError("não deve chamar a Meta")):
        resp = await client.get("/api/v1/marketing/synced-overview", headers=headers)
    body = resp.json()
    assert body["campaign_counts"] == {"c1": {"ad_sets": 2, "ads": 1}}
    assert body["breakdowns"]["age"][0]["key"] == "25-34"
    assert body["breakdowns"]["age"][0]["impressions"] == 100
    assert body["breakdowns"]["gender"] == []

    conn.ad_account_id = "act_2"
    await sync_db.flush()
    switched = await client.get("/api/v1/marketing/synced-overview", headers=headers)
    assert switched.json()["synced_at"] is None


@pytest.mark.asyncio
async def test_disconnect_deletes_the_snapshot(client, sync_db, make_user):
    tenant_id, headers = await make_user()
    conn = await _connect(sync_db, tenant_id=tenant_id)
    sync_db.add(AdsSyncSnapshot(account_id=tenant_id, ad_account_id="act_1", data={"campaigns": []}))
    await sync_db.flush()

    handler = lambda request: httpx.Response(200, json={"success": True})
    with patch("app.routes.auth.httpx.AsyncClient",
               lambda **kw: _RealAsyncClient(transport=httpx.MockTransport(handler), **kw)):
        resp = await client.delete(f"/api/v1/auth/meta/connections/{conn.id}", headers=headers)
    assert resp.status_code == 200
    await sync_db.flush()
    assert await sync_db.get(AdsSyncSnapshot, tenant_id) is None


@pytest.mark.asyncio
async def test_data_deletion_purges_the_snapshot(sync_db):
    conn = await _connect(sync_db)
    sync_db.add(AdsSyncSnapshot(account_id=conn.account_id, ad_account_id="act_1", data={"campaigns": []}))
    await sync_db.flush()
    await purge_meta_user_data(sync_db, conn.meta_user_id)
    assert await sync_db.get(AdsSyncSnapshot, conn.account_id) is None


@pytest.mark.asyncio
async def test_lifespan_runs_the_sync_only_when_enabled():
    async def _idle():
        return None

    for enabled, expected in ((True, 1), (False, 0)):
        with patch.object(app_main, "_MIGRATIONS", []), \
                patch.object(app_main, "_start_scheduler", _idle), \
                patch.object(app_main.settings, "ads_sync_enabled", enabled), \
                patch.object(ads_sync, "run_ads_sync_round", AsyncMock()) as round_mock:
            async with lifespan(app):
                import asyncio
                await asyncio.sleep(0.01)
            assert round_mock.await_count == expected
    assert "ads_sync_snapshots" in Base.metadata.tables


def _ig_transport(status, body, calls):
    def handler(request):
        calls.append(request)
        return httpx.Response(status, text=body) if isinstance(body, str) else httpx.Response(status, json=body)

    return patch.object(
        instagram_service.httpx, "AsyncClient",
        lambda **kw: _RealAsyncClient(transport=httpx.MockTransport(handler), **kw),
    )


@pytest.mark.parametrize("body", ["Internal Server Error", {"error": {"code": 2, "message": "oops"}}])
@pytest.mark.asyncio
async def test_commenter_profile_500_is_not_retried_and_keeps_the_username(body):
    calls = []
    with _ig_transport(500, body, calls), patch("asyncio.sleep", AsyncMock()) as sleep:
        ctx = await _build_person_context("tok", "111", "fulano")
    assert len(calls) == 1
    sleep.assert_not_awaited()
    assert ctx == {"usuario": "fulano", "nome": "fulano", "primeiro_nome": "fulano"}


@pytest.mark.asyncio
async def test_dm_profile_still_retries_on_500():
    calls = []
    with _ig_transport(500, {"error": {"code": 2}}, calls), patch("asyncio.sleep", AsyncMock()):
        await instagram_service.get_user_profile("tok", "111")
    assert len(calls) == 3
