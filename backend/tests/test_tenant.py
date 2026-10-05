"""
Tests for tenant isolation: MetaConnection queries must not leak across accounts.
"""
import pytest
from sqlalchemy import select

from app.models.meta_connection import MetaConnection, STATUS_ACTIVE
from app.services.meta_token_service import encrypt_token


def _make_connection(account_id: str, provider: str, page_id: str) -> MetaConnection:
    return MetaConnection(
        account_id=account_id,
        provider=provider,
        page_id=page_id,
        access_token_encrypted=encrypt_token("fake_token"),
        status=STATUS_ACTIVE,
    )


@pytest.mark.asyncio
async def test_connections_isolated_by_account(db_session):
    conn_a = _make_connection("account-A", "instagram", "page-1")
    conn_b = _make_connection("account-B", "instagram", "page-2")
    db_session.add_all([conn_a, conn_b])
    await db_session.flush()

    result = await db_session.execute(
        select(MetaConnection).where(MetaConnection.account_id == "account-A")
    )
    rows = result.scalars().all()

    assert len(rows) == 1
    assert rows[0].page_id == "page-1"
    assert all(r.account_id == "account-A" for r in rows)


@pytest.mark.asyncio
async def test_api_connections_endpoint_isolates_tenant(client, db_session):
    from app.core.security import create_access_token, hash_password
    from app.models.account import Account
    from app.models.user import User
    acc = Account(id="tenant-alpha", brand_name="Alpha")
    db_session.add(acc)
    usr = User(id="u1", tenant_id="tenant-alpha", username="alpha@t.com", password_hash=hash_password("x"), role="admin")
    db_session.add(usr)
    conn_a = _make_connection("tenant-alpha", "ads", "page-alpha")
    conn_b = _make_connection("tenant-beta", "ads", "page-beta")
    db_session.add_all([conn_a, conn_b])
    await db_session.flush()

    resp = await client.get(
        "/api/v1/auth/meta/connections",
        params={"account_id": "tenant-alpha"},
        headers={"Authorization": f"Bearer {create_access_token('u1', 'tenant-alpha', 'admin')}"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert data[0]["page_id"] == "page-alpha"


@pytest.mark.asyncio
async def test_delete_rejects_wrong_tenant(client, db_session):
    conn = _make_connection("owner-account", "instagram", "page-owner")
    db_session.add(conn)
    await db_session.flush()
    await db_session.refresh(conn)

    # Attempt to delete from a different tenant
    resp = await client.delete(
        f"/api/v1/auth/meta/connections/{conn.id}",
        params={"account_id": "attacker-account"},
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_multiple_providers_per_account(db_session):
    for provider in ("instagram", "whatsapp", "ads"):
        conn = _make_connection("multi-tenant", provider, f"page-{provider}")
        db_session.add(conn)
    await db_session.flush()

    result = await db_session.execute(
        select(MetaConnection).where(MetaConnection.account_id == "multi-tenant")
    )
    rows = result.scalars().all()
    providers = {r.provider for r in rows}
    assert providers == {"instagram", "whatsapp", "ads"}
