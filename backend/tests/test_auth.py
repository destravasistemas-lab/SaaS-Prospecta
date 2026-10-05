"""
Tests for OAuth state signing and the connections endpoints.
"""
import pytest
from cryptography.fernet import Fernet

from app.services.meta_token_service import (
    create_signed_state,
    verify_signed_state,
    encrypt_token,
    decrypt_token,
)
from app.core.config import settings


# ---------------------------------------------------------------------------
# Signed state
# ---------------------------------------------------------------------------

def test_state_roundtrip():
    state = create_signed_state("acc-123", "instagram")
    payload = verify_signed_state(state)
    assert payload["account_id"] == "acc-123"
    assert payload["provider"] == "instagram"


def test_state_tampered_signature():
    state = create_signed_state("acc-123", "instagram")
    # Flip the last character of the signature
    bad_state = state[:-1] + ("0" if state[-1] != "0" else "1")
    with pytest.raises(ValueError, match="Invalid state signature"):
        verify_signed_state(bad_state)


def test_state_missing_dot():
    with pytest.raises(ValueError, match="Malformed state"):
        verify_signed_state("nodothere")


def test_state_expired(monkeypatch):
    import time
    # Create a state with ts far in the past
    import app.services.meta_token_service as svc
    original_time = svc.time.time

    monkeypatch.setattr(svc.time, "time", lambda: original_time() - 700)
    old_state = create_signed_state("acc-x", "ads")

    monkeypatch.setattr(svc.time, "time", original_time)
    with pytest.raises(ValueError, match="expired"):
        verify_signed_state(old_state)


# ---------------------------------------------------------------------------
# Token encryption
# ---------------------------------------------------------------------------

def test_encrypt_decrypt_roundtrip():
    token = "EAABsbCS...long_real_token"
    enc = encrypt_token(token)
    assert enc != token
    assert decrypt_token(enc) == token


def test_decrypt_wrong_key():
    token = "EAABsbCS...long_real_token"
    enc = encrypt_token(token)
    # Temporarily swap the Fernet key
    import app.services.meta_token_service as svc
    original_fernet = svc._fernet
    svc._fernet = Fernet(Fernet.generate_key())
    try:
        with pytest.raises(ValueError, match="decryption failed"):
            decrypt_token(enc)
    finally:
        svc._fernet = original_fernet


# ---------------------------------------------------------------------------
# Connections endpoints (tenant isolation)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_connections_empty_for_unknown_account(client, db_session):
    from app.core.security import create_access_token, hash_password
    from app.models.account import Account
    from app.models.user import User
    import uuid
    tid = str(uuid.uuid4())
    acc = Account(id=tid, brand_name="Test")
    db_session.add(acc)
    usr = User(id="test-user", tenant_id=tid, username="test@u.com", password_hash=hash_password("x"), role="admin")
    db_session.add(usr)
    await db_session.flush()
    token = create_access_token("test-user", tid, "admin")
    resp = await client.get(
        "/api/v1/auth/meta/connections",
        params={"account_id": tid},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    assert resp.json() == []


@pytest.mark.asyncio
async def test_start_rejects_invalid_provider(client):
    resp = await client.get(
        "/api/v1/auth/meta/start",
        params={"account_id": "acc-123", "provider": "twitter"},
    )
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_start_returns_auth_url(client):
    for provider in ("instagram", "whatsapp", "ads"):
        resp = await client.get(
            "/api/v1/auth/meta/start",
            params={"account_id": "acc-123", "provider": provider},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "auth_url" in data
        assert "facebook.com" in data["auth_url"]
        assert f"state=" in data["auth_url"]


@pytest.mark.asyncio
async def test_delete_connection_not_found(client):
    resp = await client.delete(
        "/api/v1/auth/meta/connections/nonexistent-id",
        params={"account_id": "acc-123"},
    )
    assert resp.status_code == 404
