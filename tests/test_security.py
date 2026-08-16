import pytest

@pytest.mark.asyncio
async def test_missing_api_key_rejected(client):
    r = await client.post("/auth/login", json={"email": "a@test.com", "password": "Password123"})
    assert r.status_code in (401, 422)

@pytest.mark.asyncio
async def test_invalid_token_rejected(client, tenant_keys):
    headers = {**tenant_keys, "Authorization": "Bearer invalid.token.here"}
    r = await client.get("/profile", headers=headers)
    assert r.status_code == 401

@pytest.mark.asyncio
async def test_sql_injection_in_email_field(client, tenant_keys):
    r = await client.post("/auth/login", json={"email": "' OR '1'='1", "password": "x"}, headers=tenant_keys)
    assert r.status_code in (401, 422)

@pytest.mark.asyncio
async def test_rate_limit_login(client, tenant_keys):
    await client.post("/auth/register", json={"email": "ratelimit@test.com", "password": "Password123"}, headers=tenant_keys)
    responses = []
    for _ in range(25):
        r = await client.post("/auth/login", json={"email": "ratelimit@test.com", "password": "WrongPass1"}, headers=tenant_keys)
        responses.append(r.status_code)
    assert 429 in responses or 423 in responses

@pytest.mark.asyncio
async def test_cross_tenant_token_rejected(client, tenant_keys):
    r = await client.post("/tenant/register", json={"name": "T2", "email": "t2@test.com", "password": "Password123"})
    other_keys = {"X-API-Key": r.json()["data"]["secret_key"]}

    r2 = await client.post("/auth/register", json={"email": "x@test.com", "password": "Password123"}, headers=tenant_keys)
    access = r2.json()["data"]["access_token"]

    r3 = await client.get("/profile", headers={**other_keys, "Authorization": f"Bearer {access}"})
    assert r3.status_code == 401