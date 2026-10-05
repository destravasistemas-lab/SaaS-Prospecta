"""
Tests for webhook signature validation, event routing, and lead capture.
"""
import hashlib
import hmac
import json
import pytest
from sqlalchemy import select
from unittest.mock import AsyncMock, patch

from app.routes.webhook import _verify_signature
from app.models.account import Account
from app.models.lead import Lead, LeadSource
from app.models.automation import AutomationConfig


APP_SECRET = "test_app_secret"


@pytest.fixture(autouse=True)
def _mock_ig_profile():
    """Perfil fixo do remetente/comentarista — evita chamada de rede na personalização."""
    with patch(
        "app.services.instagram_service.get_user_profile",
        new_callable=AsyncMock,
        return_value={"name": "Carla Souza", "username": "carla", "profile_pic": None},
    ):
        yield


def _make_signature(body: bytes, secret: str = APP_SECRET) -> str:
    sig = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    return f"sha256={sig}"


async def _signed_post(client, payload: dict):
    body = json.dumps(payload).encode()
    return await client.post(
        "/api/v1/webhook/meta",
        content=body,
        headers={
            "Content-Type": "application/json",
            "X-Hub-Signature-256": _make_signature(body),
        },
    )


# ---------------------------------------------------------------------------
# Signature validation (pure functions)
# ---------------------------------------------------------------------------

def test_valid_signature():
    body = b'{"object":"instagram","entry":[]}'
    assert _verify_signature(body, _make_signature(body)) is True


def test_invalid_signature_wrong_secret():
    body = b'{"object":"instagram","entry":[]}'
    assert _verify_signature(body, _make_signature(body, "wrong")) is False


def test_valid_signature_from_instagram_app_secret(monkeypatch):
    """Webhook do Instagram é assinado com IG_APP_SECRET, não META_APP_SECRET."""
    from app.core.config import settings
    monkeypatch.setattr(settings, "ig_app_secret", "ig_secret_xyz")
    body = b'{"object":"instagram","entry":[]}'
    # Assinado com o secret do app do Instagram (diferente do principal)
    assert _verify_signature(body, _make_signature(body, "ig_secret_xyz")) is True
    # E o secret do app principal continua válido
    assert _verify_signature(body, _make_signature(body)) is True


def test_tampered_body():
    body = b'{"object":"instagram","entry":[]}'
    sig = _make_signature(body)
    assert _verify_signature(b'{"object":"evil"}', sig) is False


def test_missing_prefix():
    body = b'{"object":"instagram"}'
    bare = hmac.new(APP_SECRET.encode(), body, hashlib.sha256).hexdigest()
    assert _verify_signature(body, bare) is False


def test_empty_signature():
    assert _verify_signature(b'{}', "") is False


# ---------------------------------------------------------------------------
# GET challenge verification
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_challenge_ok(client):
    resp = await client.get(
        "/api/v1/webhook/meta",
        params={"hub.mode": "subscribe", "hub.verify_token": "test_verify_token", "hub.challenge": "99"},
    )
    assert resp.status_code == 200
    assert resp.json() == 99


@pytest.mark.asyncio
async def test_challenge_wrong_token(client):
    resp = await client.get(
        "/api/v1/webhook/meta",
        params={"hub.mode": "subscribe", "hub.verify_token": "wrong", "hub.challenge": "99"},
    )
    assert resp.status_code == 403


# ---------------------------------------------------------------------------
# POST — signature enforcement
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_post_rejects_unsigned(client):
    body = json.dumps({"object": "instagram", "entry": []}).encode()
    resp = await client.post(
        "/api/v1/webhook/meta",
        content=body,
        headers={"Content-Type": "application/json"},
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_post_accepts_signed_empty(client):
    resp = await _signed_post(client, {"object": "instagram", "entry": []})
    assert resp.status_code == 200
    assert resp.json() == {"status": "received"}


# ---------------------------------------------------------------------------
# Lead capture — IG comment
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_ig_comment_creates_lead(client, db_session):
    # Cria uma conta (tenant)
    account = Account(
        brand_name="Teste",
        meta_page_id="PAGE_001",
        meta_page_name="Página Teste",
        meta_access_token="fake_token",
    )
    db_session.add(account)
    await db_session.flush()
    await db_session.refresh(account)

    payload = {
        "object": "instagram",
        "entry": [{
            "id": "PAGE_001",
            "changes": [{
                "field": "comments",
                "value": {
                    "from": {"id": "USER_123", "username": "joao_silva"},
                    "id": "COMMENT_001",
                    "text": "Quero saber mais sobre o produto!",
                },
            }],
        }],
    }

    with patch("app.services.instagram_service.reply_to_comment", new_callable=AsyncMock):
        resp = await _signed_post(client, payload)

    assert resp.status_code == 200

    result = await db_session.execute(
        select(Lead).where(Lead.account_id == account.id)
    )
    leads = result.scalars().all()
    assert len(leads) == 1
    # Lead é chaveado pelo IGSID (from.id) para casar com o DM; nome guarda o @
    assert leads[0].instagram_handle == "USER_123"
    assert leads[0].name == "joao_silva"
    assert leads[0].source == LeadSource.INSTAGRAM_COMMENT


@pytest.mark.asyncio
async def test_ig_comment_does_not_duplicate_lead(client, db_session):
    account = Account(
        brand_name="Dup Test",
        meta_page_id="PAGE_002",
        meta_page_name="Página Dup",
        meta_access_token="fake_token",
    )
    db_session.add(account)
    await db_session.flush()

    payload = {
        "object": "instagram",
        "entry": [{
            "id": "PAGE_002",
            "changes": [{
                "field": "comments",
                "value": {"from": {"id": "U1", "username": "maria"}, "id": "C1", "text": "oi"},
            }],
        }],
    }

    with patch("app.services.instagram_service.reply_to_comment", new_callable=AsyncMock):
        await _signed_post(client, payload)
        await _signed_post(client, payload)  # segundo comentário da mesma pessoa

    result = await db_session.execute(
        select(Lead).where(Lead.account_id == account.id, Lead.instagram_handle == "U1")
    )
    assert len(result.scalars().all()) == 1


# ---------------------------------------------------------------------------
# Auto-reply via keyword match
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_keyword_triggers_auto_reply(client, db_session):
    account = Account(
        brand_name="AutoReply Test",
        meta_page_id="PAGE_003",
        meta_page_name="Página AR",
        meta_access_token="fake_token",
    )
    db_session.add(account)
    await db_session.flush()
    await db_session.refresh(account)

    config = AutomationConfig(
        account_id=account.id,
        keyword="quero",
        auto_reply_message="Olá! Em breve te respondo 😊",
        trigger_type="comment",
        media_id="POST_AR",
        is_active=True,
    )
    db_session.add(config)
    await db_session.flush()

    payload = {
        "object": "instagram",
        "entry": [{
            "id": "PAGE_003",
            "changes": [{
                "field": "comments",
                "value": {"from": {"id": "U2", "username": "pedro"}, "media": {"id": "POST_AR"},
                          "id": "C2", "text": "Quero comprar!"},
            }],
        }],
    }

    with patch("app.services.instagram_service.reply_to_comment", new_callable=AsyncMock) as mock_reply:
        await _signed_post(client, payload)
        mock_reply.assert_called_once()
        _, comment_id, msg = mock_reply.call_args[0]
        assert comment_id == "C2"
        assert msg == "Olá! Em breve te respondo 😊"


@pytest.mark.asyncio
async def test_comment_keyword_sends_private_dm(client, db_session):
    account = Account(
        brand_name="DM Test",
        meta_page_id="PAGE_005",
        meta_page_name="Página DM",
        meta_access_token="fake_token",
    )
    db_session.add(account)
    await db_session.flush()
    await db_session.refresh(account)

    config = AutomationConfig(
        account_id=account.id,
        keyword="quero",
        auto_reply_message="Fallback",
        comment_reply_message="Te chamei no direto!",
        dm_message="Aqui está o link que você pediu 😉",
        trigger_type="comment",
        media_id="POST_DM",
        is_active=True,
    )
    db_session.add(config)
    await db_session.flush()

    payload = {
        "object": "instagram",
        "entry": [{
            "id": "PAGE_005",
            "changes": [{
                "field": "comments",
                "value": {"from": {"id": "U5", "username": "carla"}, "media": {"id": "POST_DM"},
                          "id": "C5", "text": "Quero saber mais!"},
            }],
        }],
    }

    with patch("app.services.instagram_service.reply_to_comment", new_callable=AsyncMock) as mock_reply, \
         patch("app.services.instagram_service.send_private_reply", new_callable=AsyncMock) as mock_dm:
        await _signed_post(client, payload)
        mock_reply.assert_called_once()
        assert mock_reply.call_args[0][2] == "Te chamei no direto!"
        mock_dm.assert_called_once()
        assert mock_dm.call_args[0][1] == "C5"
        assert mock_dm.call_args[0][2] == "Aqui está o link que você pediu 😉"


@pytest.mark.asyncio
async def test_comment_dm_personalization_substitutes_name(client, db_session):
    """{{primeiro_nome}} / {{usuario}} são trocados pelo nome real de quem comentou."""
    account = Account(
        brand_name="Perso Test",
        meta_page_id="PAGE_PERSO",
        meta_page_name="Página Perso",
        meta_access_token="fake_token",
    )
    db_session.add(account)
    await db_session.flush()

    config = AutomationConfig(
        account_id=account.id,
        keyword="quero",
        auto_reply_message="Fallback",
        comment_reply_message="Te chamei no direto, {{primeiro_nome}}! 📩",
        dm_message="Oi {{nome}} (@{{usuario}})! Aqui está o que você pediu 👇",
        trigger_type="comment",
        media_id="POST_PERSO",
        is_active=True,
    )
    db_session.add(config)
    await db_session.flush()

    payload = {
        "object": "instagram",
        "entry": [{
            "id": "PAGE_PERSO",
            "changes": [{
                "field": "comments",
                "value": {"from": {"id": "U9", "username": "carla"}, "media": {"id": "POST_PERSO"},
                          "id": "C9", "text": "Quero!"},
            }],
        }],
    }

    with patch("app.services.instagram_service.reply_to_comment", new_callable=AsyncMock) as mock_reply, \
         patch("app.services.instagram_service.send_private_reply", new_callable=AsyncMock) as mock_dm:
        await _signed_post(client, payload)
        # {{primeiro_nome}} → "Carla" (do perfil mockado)
        assert mock_reply.call_args[0][2] == "Te chamei no direto, Carla! 📩"
        # {{nome}} → "Carla Souza", {{usuario}} → "carla"
        assert mock_dm.call_args[0][2] == "Oi Carla Souza (@carla)! Aqui está o que você pediu 👇"


@pytest.mark.asyncio
async def test_automation_scoped_to_other_media_does_not_match(client, db_session):
    account = Account(
        brand_name="Media Scope Test",
        meta_page_id="PAGE_006",
        meta_page_name="Página Scope",
        meta_access_token="fake_token",
    )
    db_session.add(account)
    await db_session.flush()
    await db_session.refresh(account)

    config = AutomationConfig(
        account_id=account.id,
        keyword="quero",
        auto_reply_message="Fallback",
        dm_message="Só deveria disparar no post MEDIA_A",
        media_id="MEDIA_A",
        trigger_type="both",
        is_active=True,
    )
    db_session.add(config)
    await db_session.flush()

    payload = {
        "object": "instagram",
        "entry": [{
            "id": "PAGE_006",
            "changes": [{
                "field": "comments",
                "value": {
                    "from": {"id": "U6", "username": "bruno"},
                    "id": "C6",
                    "text": "Quero saber mais!",
                    "media": {"id": "MEDIA_B"},
                },
            }],
        }],
    }

    with patch("app.services.instagram_service.reply_to_comment", new_callable=AsyncMock) as mock_reply, \
         patch("app.services.instagram_service.send_private_reply", new_callable=AsyncMock) as mock_dm:
        await _signed_post(client, payload)
        mock_reply.assert_not_called()
        mock_dm.assert_not_called()


@pytest.mark.asyncio
async def test_no_match_no_reply(client, db_session):
    account = Account(
        brand_name="NoMatch Test",
        meta_page_id="PAGE_004",
        meta_page_name="Página NM",
        meta_access_token="fake_token",
    )
    db_session.add(account)
    await db_session.flush()
    await db_session.refresh(account)

    config = AutomationConfig(
        account_id=account.id,
        keyword="preco",
        auto_reply_message="Nosso preço é R$ 99",
        is_active=True,
    )
    db_session.add(config)
    await db_session.flush()

    payload = {
        "object": "instagram",
        "entry": [{
            "id": "PAGE_004",
            "changes": [{
                "field": "comments",
                "value": {"from": {"id": "U3", "username": "ana"}, "id": "C3", "text": "adorei o post!"},
            }],
        }],
    }

    with patch("app.services.instagram_service.reply_to_comment", new_callable=AsyncMock) as mock_reply:
        await _signed_post(client, payload)
        mock_reply.assert_not_called()
