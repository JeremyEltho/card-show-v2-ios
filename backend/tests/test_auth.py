"""Tests for auth endpoints."""
import pytest
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker

from main import app
from app.core.database import Base, get_db

TEST_DB = "sqlite+aiosqlite:///:memory:"


@pytest.fixture
async def async_client():
    engine = create_async_engine(TEST_DB)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async def override_get_db():
        async with session_factory() as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        yield client

    app.dependency_overrides.clear()
    await engine.dispose()


@pytest.mark.asyncio
async def test_register(async_client):
    resp = await async_client.post("/api/v1/auth/register", json={
        "email": "test@example.com",
        "password": "password123",
        "display_name": "Test",
    })
    assert resp.status_code == 201
    data = resp.json()
    assert "access_token" in data
    assert data["user"]["email"] == "test@example.com"


@pytest.mark.asyncio
async def test_login(async_client):
    await async_client.post("/api/v1/auth/register", json={
        "email": "login@example.com",
        "password": "password123",
        "display_name": "Login Test",
    })
    resp = await async_client.post("/api/v1/auth/login", json={
        "email": "login@example.com",
        "password": "password123",
    })
    assert resp.status_code == 200
    assert "access_token" in resp.json()


@pytest.mark.asyncio
async def test_login_wrong_password(async_client):
    await async_client.post("/api/v1/auth/register", json={
        "email": "bad@example.com",
        "password": "correct",
        "display_name": "Bad",
    })
    resp = await async_client.post("/api/v1/auth/login", json={
        "email": "bad@example.com",
        "password": "wrong",
    })
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_duplicate_register(async_client):
    payload = {"email": "dupe@example.com", "password": "password123", "display_name": "Dupe"}
    await async_client.post("/api/v1/auth/register", json=payload)
    resp = await async_client.post("/api/v1/auth/register", json=payload)
    assert resp.status_code == 409


@pytest.mark.asyncio
async def test_protected_endpoint_requires_auth(async_client):
    resp = await async_client.get("/api/v1/inventory")
    assert resp.status_code == 403
