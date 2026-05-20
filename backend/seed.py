"""
Seed the database with a test user and sample inventory for development/demo.
Run: python seed.py
"""
import asyncio
import uuid
from datetime import datetime, timezone, timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import AsyncSessionLocal, engine, Base
from app.core.security import hash_password
from app.models.user import User, RefreshToken
from app.models.inventory import InventoryItem, Transaction
from app.models.card_cache import CardCache, PriceCache

SAMPLE_CARDS = [
    {
        "card_id": "base1-4",
        "name": "Charizard",
        "set_name": "Base Set",
        "purchase_price": 500.00,
        "market_price": 595.18,
        "status": "bought",
    },
    {
        "card_id": "base1-10",
        "name": "Mewtwo",
        "set_name": "Base Set",
        "purchase_price": 80.00,
        "market_price": 120.00,
        "status": "holding",
    },
    {
        "card_id": "base1-15",
        "name": "Venusaur",
        "set_name": "Base Set",
        "purchase_price": 60.00,
        "market_price": 90.00,
        "status": "holding",
    },
    {
        "card_id": "base1-16",
        "name": "Zapdos",
        "set_name": "Base Set",
        "purchase_price": 40.00,
        "sale_price": 75.00,
        "market_price": 70.00,
        "status": "sold",
    },
    {
        "card_id": "sv1-6",
        "name": "Charizard ex",
        "set_name": "Scarlet & Violet",
        "purchase_price": 35.00,
        "market_price": 55.00,
        "status": "holding",
    },
]


async def seed():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with AsyncSessionLocal() as db:
        # Create demo user
        result = await db.execute(
            __import__("sqlalchemy").select(User).where(User.email == "demo@pokescan.com")
        )
        user = result.scalar_one_or_none()
        if not user:
            user = User(
                email="demo@pokescan.com",
                hashed_password=hash_password("pokemon123"),
                display_name="Demo Trainer",
            )
            db.add(user)
            await db.flush()
            print(f"Created user: {user.email} (password: pokemon123)")
        else:
            print(f"User already exists: {user.email}")

        # Add sample inventory
        now = datetime.now(timezone.utc)
        for i, card_data in enumerate(SAMPLE_CARDS):
            # Check if already exists
            existing = await db.execute(
                __import__("sqlalchemy").select(InventoryItem).where(
                    InventoryItem.user_id == user.id,
                    InventoryItem.card_id == card_data["card_id"],
                    InventoryItem.deleted_at.is_(None),
                )
            )
            if existing.scalar_one_or_none():
                print(f"  Skipping {card_data['name']} (already seeded)")
                continue

            acquired = now - timedelta(days=i * 3)
            item = InventoryItem(
                user_id=user.id,
                card_id=card_data["card_id"],
                status=card_data["status"],
                condition="near_mint",
                quantity=1,
                purchase_price=card_data.get("purchase_price"),
                sale_price=card_data.get("sale_price"),
                market_price_at_scan=card_data.get("market_price"),
                source_location="Demo Show 2026",
                acquired_at=acquired,
                sold_at=(acquired + timedelta(days=1)) if card_data["status"] == "sold" else None,
                client_id=str(uuid.uuid4()),
            )
            db.add(item)
            await db.flush()

            # Add transaction
            tx_type = "purchase" if card_data["status"] in ("bought", "holding") else "sale"
            tx_price = card_data.get("sale_price") or card_data.get("purchase_price", 0)
            db.add(Transaction(
                user_id=user.id,
                inventory_item_id=item.id,
                type=tx_type,
                price=tx_price,
                quantity=1,
                location="Demo Show 2026",
                client_id=str(uuid.uuid4()),
            ))
            print(f"  Added {card_data['name']} ({card_data['status']}, ${tx_price})")

        await db.commit()
        print("\nSeed complete. Login: demo@pokescan.com / pokemon123")


if __name__ == "__main__":
    asyncio.run(seed())
