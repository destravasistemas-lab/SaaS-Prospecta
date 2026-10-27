"""
Estados vazios sem 404, CORS em respostas de erro e corrida do /ai/config.
"""
import uuid

import pytest

from app.core.config import settings
from app.core.database import get_db
from app.services.meta_token_service import encrypt_token
from app.main import app
from app.models.ai import AIConfig, DEFAULT_SYSTEM_PROMPT
from app.models.meta_connection import MetaConnection, PROVIDER_WHATSAPP, STATUS_ACTIVE
from app.routes import ai as ai_routes

ORIGIN = settings.cors_origins_list[0]


@pytest.mark.asyncio
async def test_credentials_not_connected_returns_200(client, make_user):
    _, headers = await make_user()
    r = await client.get("/api/v1/whatsapp/credentials", headers=headers)
    assert r.status_code == 200
    assert r.json() == {"connected": False, "credentials": None}


@pytest.mark.asyncio
async def test_credentials_connected(client, make_user, db_session):
    tid, headers = await make_user()
    db_session.add(MetaConnection(
        id=str(uuid.uuid4()), account_id=tid, provider=PROVIDER_WHATSAPP,
        phone_number_id="123", phone_number="+55 11 99999-0000", waba_id="456",
        access_token_encrypted=encrypt_token("tok"), status=STATUS_ACTIVE,
    ))
    await db_session.flush()
    r = await client.get("/api/v1/whatsapp/credentials", headers=headers)
    assert r.status_code == 200
    body = r.json()
    assert body["connected"] is True
    assert body["credentials"]["phone_number"] == "+55 11 99999-0000"


@pytest.mark.asyncio
async def test_costs_not_connected_returns_zeros(client, make_user):
    _, headers = await make_user()
    r = await client.get("/api/v1/whatsapp/costs", headers=headers)
    assert r.status_code == 200
    body = r.json()
    assert body["connected"] is False
    assert body["total"] == 0
    assert all(b["count"] == 0 for b in body["breakdown"].values())


@pytest.mark.asyncio
async def test_401_has_cors_headers(client):
    r = await client.get("/api/v1/ai/config", headers={"Origin": ORIGIN})
    assert r.status_code == 401
    assert r.headers.get("access-control-allow-origin") == ORIGIN


@pytest.mark.asyncio
async def test_unhandled_500_has_cors_headers(client):
    async def _broken_db():
        raise RuntimeError("db down")
        yield

    app.dependency_overrides[get_db] = _broken_db
    r = await client.get(
        "/api/v1/ai/config",
        headers={"Origin": ORIGIN, "Authorization": "Bearer x", "X-Lang": "en"},
    )
    assert r.status_code == 500
    assert r.json() == {"detail": "Internal server error."}
    assert r.headers.get("access-control-allow-origin") == ORIGIN


@pytest.mark.asyncio
async def test_ai_config_create_race_reuses_existing_row(make_user, db_session, monkeypatch):
    tid, _ = await make_user()
    winner = AIConfig(account_id=tid, system_prompt=DEFAULT_SYSTEM_PROMPT)
    db_session.add(winner)
    await db_session.flush()

    real_find = ai_routes._find_config
    calls = 0

    async def _find_missing_first(db, account_id):
        nonlocal calls
        calls += 1
        return None if calls == 1 else await real_find(db, account_id)

    monkeypatch.setattr(ai_routes, "_find_config", _find_missing_first)
    cfg = await ai_routes._get_or_create_config(db_session, tid)
    assert cfg.id == winner.id
