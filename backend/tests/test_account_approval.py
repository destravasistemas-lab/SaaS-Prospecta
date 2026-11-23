"""Cadastro novo só entra no painel depois que o super admin aprova."""
import uuid

import pytest

from app.core.config import settings
from app.core.security import create_access_token, hash_password
from app.models.account import Account
from app.models.user import User


@pytest.fixture
def super_admin_email(monkeypatch):
    email = f"root-{uuid.uuid4().hex[:6]}@destrava.com"
    monkeypatch.setattr(settings, "super_admin_emails", email)
    return email


async def _register(client, email):
    return await client.post("/api/v1/auth/register", json={
        "brand_name": "Clínica Nova", "username": email, "password": "segredo1", "full_name": "Ana",
    })


async def _login(client, email, password="segredo1"):
    return await client.post("/api/v1/auth/login", json={"username": email, "password": password})


async def _super_admin_headers(db_session, email):
    tid, uid = str(uuid.uuid4()), str(uuid.uuid4())
    db_session.add(Account(id=tid, brand_name="Destrava"))
    db_session.add(User(id=uid, tenant_id=tid, username=email, password_hash=hash_password("x"), role="admin"))
    await db_session.flush()
    return {"Authorization": f"Bearer {create_access_token(uid, tid, 'admin')}"}


async def test_signup_waits_for_approval_and_gets_no_token(client):
    email = f"{uuid.uuid4().hex[:8]}@clinica.com"
    r = await _register(client, email)
    assert r.status_code == 201
    assert r.json()["status"] == "pending"
    assert "access_token" not in r.json()

    r = await _login(client, email)
    assert r.status_code == 403
    assert r.json()["detail"]["code"] == "pending_approval"


async def test_wrong_password_does_not_reveal_pending_status(client):
    email = f"{uuid.uuid4().hex[:8]}@clinica.com"
    await _register(client, email)
    r = await _login(client, email, "errada")
    assert r.status_code == 401


async def test_token_of_pending_account_is_refused(client, db_session):
    tid, uid = str(uuid.uuid4()), str(uuid.uuid4())
    db_session.add(Account(id=tid, brand_name="X", approval_status="pending"))
    db_session.add(User(id=uid, tenant_id=tid, username=f"{uid}@x.com", password_hash=hash_password("x"), role="admin"))
    await db_session.flush()
    headers = {"Authorization": f"Bearer {create_access_token(uid, tid, 'admin')}"}

    r = await client.get("/api/v1/auth/me", headers=headers)
    assert r.status_code == 403
    assert r.json()["detail"]["code"] == "pending_approval"


async def test_super_admin_approves_then_user_logs_in(client, db_session, super_admin_email):
    email = f"{uuid.uuid4().hex[:8]}@clinica.com"
    await _register(client, email)
    admin = await _super_admin_headers(db_session, super_admin_email)

    tenants = (await client.get("/api/v1/admin/tenants", headers=admin)).json()
    assert tenants[0]["approval_status"] == "pending"
    mine = next(t for t in tenants if t["owner_email"] == email)

    r = await client.post(f"/api/v1/admin/tenants/{mine['id']}/approval", json={"approved": True}, headers=admin)
    assert r.status_code == 200
    assert r.json()["approval_status"] == "approved"

    r = await _login(client, email)
    assert r.status_code == 200
    me = await client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {r.json()['access_token']}"})
    assert me.status_code == 200


async def test_rejected_account_cannot_log_in(client, db_session, super_admin_email):
    email = f"{uuid.uuid4().hex[:8]}@clinica.com"
    await _register(client, email)
    admin = await _super_admin_headers(db_session, super_admin_email)
    mine = next(t for t in (await client.get("/api/v1/admin/tenants", headers=admin)).json() if t["owner_email"] == email)

    await client.post(f"/api/v1/admin/tenants/{mine['id']}/approval", json={"approved": False}, headers=admin)
    r = await _login(client, email)
    assert r.status_code == 403
    assert r.json()["detail"]["code"] == "account_rejected"


async def test_only_super_admin_can_approve(client, make_user):
    _, headers = await make_user()
    r = await client.post(f"/api/v1/admin/tenants/{uuid.uuid4()}/approval", json={"approved": True}, headers=headers)
    assert r.status_code == 403


async def test_existing_accounts_stay_approved(client, make_user):
    _, headers = await make_user()
    r = await client.get("/api/v1/auth/me", headers=headers)
    assert r.status_code == 200
