"""Tests for scan identification endpoint."""
import pytest
from unittest.mock import AsyncMock, patch
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


@pytest.fixture
async def auth_token(async_client):
    await async_client.post("/api/v1/auth/register", json={
        "email": "scan@example.com", "password": "password123", "display_name": "Scan"
    })
    resp = await async_client.post("/api/v1/auth/login", json={
        "email": "scan@example.com", "password": "password123"
    })
    return resp.json()["access_token"]


@pytest.mark.asyncio
async def test_scan_requires_ocr_or_image(async_client, auth_token):
    resp = await async_client.post("/api/v1/scan/identify",
        headers={"Authorization": f"Bearer {auth_token}"},
        json={}
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_scan_missing_card(async_client, auth_token):
    """OCR text that matches nothing returns 422."""
    resp = await async_client.post("/api/v1/scan/identify",
        headers={"Authorization": f"Bearer {auth_token}"},
        json={"ocr_text": "xyzzy_no_such_card_42"}
    )
    assert resp.status_code == 422
