"""
Roteamento do webhook com vários tenants, recusa da Meta no auto-reply e
segredos fora dos logs do httpx.
"""
import hashlib
import hmac
import json
import logging
import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, patch

import httpx
import pytest

from app.models.account import Account
from app.models.automation import AutomationConfig
from app.models.meta_connection import (
    MetaConnection, PROVIDER_INSTAGRAM, STATUS_ACTIVE, STATUS_REVOKED,
)
from app.routes.webhook import _resolve_tenant_by_page_id
from app.services.meta_token_service import encrypt_token

APP_SECRET = "test_app_secret"
NOW = datetime.now(timezone.utc)


async def _connect(db_session, ig_id, status=STATUS_ACTIVE, age_days=0):
    account = Account(brand_name=f"IG {uuid.uuid4()}")
    db_session.add(account)
    await db_session.flush()
    db_session.add(MetaConnection(
        id=str(uuid.uuid4()), account_id=account.id, provider=PROVIDER_INSTAGRAM,
        ig_business_account_id=ig_id, meta_user_id=f"scoped-{uuid.uuid4()}",
        access_token_encrypted=encrypt_token("tok"), status=status,
        updated_at=NOW - timedelta(days=age_days),
    ))
    await db_session.flush()
    return account


@pytest.mark.asyncio
async def test_revoked_connection_on_other_tenant_is_ignored(db_session):
    ig_id = str(uuid.uuid4())
    await _connect(db_session, ig_id, status=STATUS_REVOKED, age_days=30)
    active = await _connect(db_session, ig_id)
    assert (await _resolve_tenant_by_page_id(ig_id, db_session)).id == active.id


@pytest.mark.asyncio
async def test_only_revoked_connection_resolves_to_no_tenant(db_session):
    ig_id = str(uuid.uuid4())
    await _connect(db_session, ig_id, status=STATUS_REVOKED)
    assert await _resolve_tenant_by_page_id(ig_id, db_session) is None


@pytest.mark.asyncio
async def test_two_active_tenants_use_most_recent_and_warn(db_session, caplog):
    ig_id = str(uuid.uuid4())
    await _connect(db_session, ig_id, age_days=30)
    recent = await _connect(db_session, ig_id)
    with caplog.at_level(logging.WARNING, logger="app.routes.webhook"):
        resolved = await _resolve_tenant_by_page_id(ig_id, db_session)
    assert resolved.id == recent.id
    assert "mais de um tenant" in caplog.text


@pytest.mark.asyncio
async def test_meta_refusal_is_not_logged_as_sent(client, db_session, caplog):
    ig_id = str(uuid.uuid4())
    account = await _connect(db_session, ig_id)
    db_session.add(AutomationConfig(
        id=str(uuid.uuid4()), account_id=account.id, keyword="quero", auto_reply_message="ok",
        dm_message="oi", is_active=True, trigger_type="comment", media_id="MEDIA1",
    ))
    await db_session.flush()

    body = json.dumps({"object": "instagram", "entry": [{"id": ig_id, "changes": [{"field": "comments", "value": {
        "from": {"id": "111", "username": "fulano"}, "media": {"id": "MEDIA1"}, "id": "C1", "text": "quero saber",
    }}]}]}).encode()
    signature = "sha256=" + hmac.new(APP_SECRET.encode(), body, hashlib.sha256).hexdigest()
    refusal = {"error": {"code": 10, "message": "denied"}}

    with patch("app.services.instagram_service.reply_to_comment", AsyncMock(return_value=refusal)), \
         patch("app.services.instagram_service.send_private_reply", AsyncMock(return_value=refusal)), \
         patch("app.routes.webhook._build_person_context", AsyncMock(return_value={})), \
         caplog.at_level(logging.INFO, logger="app.routes.webhook"):
        resp = await client.post("/api/v1/webhook/meta", content=body, headers={
            "Content-Type": "application/json", "X-Hub-Signature-256": signature,
        })

    assert resp.status_code == 200
    assert "Auto-reply enviado" not in caplog.text
    assert "DM privada enviada" not in caplog.text
    assert "Meta recusou o auto-reply" in caplog.text
    assert "Meta recusou a DM privada" in caplog.text


def test_httpx_log_hides_secrets(caplog):
    transport = httpx.MockTransport(lambda request: httpx.Response(200, json={}))
    with caplog.at_level(logging.INFO, logger="httpx"), httpx.Client(transport=transport) as http:
        http.get("https://graph.instagram.com/access_token", params={
            "grant_type": "ig_exchange_token", "client_secret": "APPSECRET", "access_token": "USERTOKEN",
        })
    assert "APPSECRET" not in caplog.text
    assert "USERTOKEN" not in caplog.text
    assert "access_token=***" in caplog.text
    assert "200" in caplog.text
