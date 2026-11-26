"""
Antes do lançamento: limite de senha errada no login, limite de emails de
"esqueci a senha" e a marca Prospecta nos emails.
"""
import uuid
from unittest.mock import AsyncMock, patch

import pytest

from app.core import redis as redis_mod
from app.core.security import hash_password
from app.models.account import Account
from app.models.user import User
from app.services import email_service


@pytest.fixture(autouse=True)
def _fresh_store():
    redis_mod._memory.clear()
    yield
    redis_mod._memory.clear()


async def _user(db_session, password: str = "certa123") -> User:
    account = Account(id=str(uuid.uuid4()), brand_name="Loja")
    db_session.add(account)
    user = User(id=str(uuid.uuid4()), tenant_id=account.id, username=f"{uuid.uuid4()}@t.com",
                password_hash=hash_password(password), role="admin", is_active=True, is_verified=True)
    db_session.add(user)
    await db_session.flush()
    return user


@pytest.mark.asyncio
async def test_login_locks_after_ten_wrong_passwords(client, db_session):
    user = await _user(db_session)
    for _ in range(10):
        r = await client.post("/api/v1/auth/login", json={"username": user.username, "password": "errada"})
        assert r.status_code == 401
    r = await client.post("/api/v1/auth/login", json={"username": user.username, "password": "certa123"})
    assert r.status_code == 429
    # Outra conta não é afetada
    other = await _user(db_session)
    r = await client.post("/api/v1/auth/login", json={"username": other.username, "password": "certa123"})
    assert r.status_code != 429


@pytest.mark.asyncio
async def test_forgot_password_sends_at_most_three_emails_per_hour(client, db_session):
    user = await _user(db_session)
    with patch("app.routes.auth_email.send_reset_email", new_callable=AsyncMock) as send:
        for _ in range(5):
            r = await client.post("/api/v1/auth/forgot-password", json={"email": user.username})
            assert r.status_code == 200 and r.json()["success"] is True
    assert send.await_count == 3


@pytest.mark.asyncio
async def test_emails_carry_the_prospecta_brand():
    with patch.object(email_service, "send_email", new_callable=AsyncMock, return_value=True) as send:
        await email_service.send_reset_email("a@b.com", "tok", "Ana <script>")
        await email_service.send_verification_email("a@b.com", "tok", "Ana")
    subjects = [c.args[1] for c in send.await_args_list]
    assert subjects == ["Redefinir senha — Prospecta", "Confirme seu email — Prospecta"]
    html = send.await_args_list[0].args[2]
    assert "Prospecta" in html and "reset-password?token=tok" in html and "<script>" not in html
