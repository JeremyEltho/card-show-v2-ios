"""Tests for inventory endpoints."""
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


@pytest.fixture
async def auth_token(async_client):
    await async_client.post("/api/v1/auth/register", json={
        "email": "inv@example.com", "password": "password123", "display_name": "Inv"
    })
    resp = await async_client.post("/api/v1/auth/login", json={
        "email": "inv@example.com", "password": "password123"
    })
    return resp.json()["access_token"]


@pytest.mark.asyncio
async def test_empty_inventory(async_client, auth_token):
    resp = await async_client.get("/api/v1/inventory",
                                   headers={"Authorization": f"Bearer {auth_token}"})
    assert resp.status_code == 200
    assert resp.json()["total"] == 0


@pytest.mark.asyncio
async def test_add_inventory_item(async_client, auth_token):
    import uuid
    resp = await async_client.post("/api/v1/inventory",
        headers={"Authorization": f"Bearer {auth_token}"},
        json={
            "card_id": "base1-4",
            "status": "bought",
            "condition": "near_mint",
            "quantity": 1,
            "purchase_price": 500.00,
            "client_id": str(uuid.uuid4()),
        }
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["card_id"] == "base1-4"
    assert data["status"] == "bought"
    assert data["purchase_price"] == 500.0


@pytest.mark.asyncio
async def test_idempotent_add(async_client, auth_token):
    """Same client_id twice should return same item, not create duplicate."""
    import uuid
    cid = str(uuid.uuid4())
    payload = {"card_id": "base1-4", "status": "holding", "condition": "near_mint",
               "quantity": 1, "client_id": cid}
    r1 = await async_client.post("/api/v1/inventory",
        headers={"Authorization": f"Bearer {auth_token}"}, json=payload)
    r2 = await async_client.post("/api/v1/inventory",
        headers={"Authorization": f"Bearer {auth_token}"}, json=payload)

    assert r1.status_code == 201
    assert r2.status_code == 201
    assert r1.json()["id"] == r2.json()["id"]  # Same item


@pytest.mark.asyncio
async def test_update_to_sold(async_client, auth_token):
    import uuid
    add = await async_client.post("/api/v1/inventory",
        headers={"Authorization": f"Bearer {auth_token}"},
        json={"card_id": "base1-4", "status": "bought", "condition": "near_mint",
              "quantity": 1, "purchase_price": 500.0, "client_id": str(uuid.uuid4())}
    )
    item_id = add.json()["id"]

    update = await async_client.patch(f"/api/v1/inventory/{item_id}",
        headers={"Authorization": f"Bearer {auth_token}"},
        json={"status": "sold", "sale_price": 650.0}
    )
    assert update.status_code == 200
    assert update.json()["status"] == "sold"
    assert update.json()["sale_price"] == 650.0


@pytest.mark.asyncio
async def test_soft_delete(async_client, auth_token):
    import uuid
    add = await async_client.post("/api/v1/inventory",
        headers={"Authorization": f"Bearer {auth_token}"},
        json={"card_id": "base1-4", "status": "holding", "condition": "near_mint",
              "quantity": 1, "client_id": str(uuid.uuid4())}
    )
    item_id = add.json()["id"]

    del_resp = await async_client.delete(f"/api/v1/inventory/{item_id}",
        headers={"Authorization": f"Bearer {auth_token}"}
    )
    assert del_resp.status_code == 204

    list_resp = await async_client.get("/api/v1/inventory",
        headers={"Authorization": f"Bearer {auth_token}"}
    )
    ids = [i["id"] for i in list_resp.json()["items"]]
    assert item_id not in ids
