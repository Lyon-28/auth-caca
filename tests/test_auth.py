import pytest

@pytest.mark.asyncio
async def test_register_success(client, tenant_keys):
    r = await client.post("/auth/register", json={"email": "user@test.com", "password": "Password123"}, headers=tenant_keys)
    assert r.status_code == 201
    body = r.json()
    assert body["success"] is True
    assert "access_token" in body["data"]

@pytest.mark.asyncio
async def test_register_weak_password(client, tenant_keys):
    r = await client.post("/auth/register", json={"email": "weak@test.com", "password": "short"}, headers=tenant_keys)
    assert r.status_code == 422

@pytest.mark.asyncio
async def test_login_wrong_password(client, tenant_keys):
    await client.post("/auth/register", json={"email": "user2@test.com", "password": "Password123"}, headers=tenant_keys)
    r = await client.post("/auth/login", json={"email": "user2@test.com", "password": "WrongPass123"}, headers=tenant_keys)
    assert r.status_code == 401
    assert r.json()["success"] is False

@pytest.mark.asyncio
async def test_refresh_rotation(client, tenant_keys):
    r = await client.post("/auth/register", json={"email": "user3@test.com", "password": "Password123"}, headers=tenant_keys)
    refresh = r.json()["data"]["refresh_token"]

    r2 = await client.post("/auth/refresh", json={"refresh_token": refresh}, headers=tenant_keys)
    assert r2.status_code == 200
    new_refresh = r2.json()["data"]["refresh_token"]
    assert new_refresh != refresh

    r3 = await client.post("/auth/refresh", json={"refresh_token": refresh}, headers=tenant_keys)
    assert r3.status_code == 401
    assert r3.json()["error"]["code"] == "token_reuse_detected"

@pytest.mark.asyncio
async def test_tenant_isolation(client, tenant_keys):
    r = await client.post("/tenant/register", json={"name": "Other Tenant", "email": "other@test.com", "password": "Password123"})
    other_keys = {"X-API-Key": r.json()["data"]["secret_key"]}

    await client.post("/auth/register", json={"email": "shared@test.com", "password": "Password123"}, headers=tenant_keys)
    r2 = await client.post("/auth/login", json={"email": "shared@test.com", "password": "Password123"}, headers=other_keys)
    assert r2.status_code == 401