import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from app.main import app
from app.database import Base, engine, SessionLocal

@pytest_asyncio.fixture(scope="function")
async def db_setup():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

@pytest_asyncio.fixture
async def client(db_setup):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac

@pytest_asyncio.fixture
async def tenant_keys(client):
    r = await client.post("/tenant/register", json={"name": "Test Tenant", "email": "tenant@test.com", "password": "Password123"})
    data = r.json()["data"]
    return {"X-API-Key": data["secret_key"]}