"""
Fetches and caches card market prices.
Hot cache: in-memory dict (5min TTL).
Warm cache: price_cache table (1hr TTL).
Cold: JustTCG API.
Fallback: pokemontcg.io tcgplayer prices embedded in card data.
"""
import json
from datetime import datetime, timezone, timedelta

import httpx
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.card_cache import PriceCache, CardCache
from app.core.config import get_settings

settings = get_settings()

PRICE_TTL_SECONDS = 3600  # 1 hour DB cache
MEMORY_TTL_SECONDS = 300  # 5 min memory cache

_price_memory: dict[str, tuple[datetime, dict]] = {}


def _memory_get(card_id: str) -> dict | None:
    if card_id in _price_memory:
        ts, val = _price_memory[card_id]
        if datetime.now(timezone.utc) - ts < timedelta(seconds=MEMORY_TTL_SECONDS):
            return val
        del _price_memory[card_id]
    return None


def _memory_set(card_id: str, val: dict) -> None:
    _price_memory[card_id] = (datetime.now(timezone.utc), val)


def _row_to_dict(row: PriceCache) -> dict:
    return {
        "card_id": row.card_id,
        "market_price": row.market_price,
        "low_price": row.low_price,
        "mid_price": row.mid_price,
        "high_price": row.high_price,
        "foil_market": row.foil_market,
        "source": row.source,
        "fetched_at": row.fetched_at.isoformat() if row.fetched_at else None,
    }


async def _fetch_justtcg(card_id: str) -> dict | None:
    if not settings.JUSTTCG_API_KEY:
        return None
    try:
        async with httpx.AsyncClient(timeout=8.0) as client:
            r = await client.get(
                f"https://api.justtcg.com/v1/prices/{card_id}",
                headers={"Authorization": f"Bearer {settings.JUSTTCG_API_KEY}"},
            )
            if r.status_code == 200:
                data = r.json()
                return {
                    "market_price": data.get("marketPrice"),
                    "low_price": data.get("lowPrice"),
                    "mid_price": data.get("midPrice"),
                    "high_price": data.get("highPrice"),
                    "foil_market": data.get("foilMarketPrice"),
                    "source": "justtcg",
                }
    except httpx.HTTPError:
        pass
    return None


async def _extract_price_from_card_cache(card_id: str, db: AsyncSession) -> dict | None:
    """Extract TCGPlayer pricing embedded in the pokemontcg.io card data."""
    result = await db.execute(select(CardCache).where(CardCache.card_id == card_id))
    row = result.scalar_one_or_none()
    if not row or not row.data_json:
        return None
    try:
        card_data = json.loads(row.data_json)
        tcg = card_data.get("tcgplayer", {}).get("prices", {})
        # Pick best variant: holofoil > reverseHolofoil > normal
        prices = tcg.get("holofoil") or tcg.get("reverseHolofoil") or tcg.get("normal") or {}
        if not prices:
            return None
        return {
            "market_price": prices.get("market"),
            "low_price": prices.get("low"),
            "mid_price": prices.get("mid"),
            "high_price": prices.get("high"),
            "foil_market": tcg.get("holofoil", {}).get("market"),
            "source": "pokemontcg_embedded",
        }
    except (json.JSONDecodeError, AttributeError):
        return None


async def get_price(card_id: str, db: AsyncSession) -> dict | None:
    # 1. Memory cache
    cached = _memory_get(card_id)
    if cached:
        return cached

    # 2. DB cache (1hr TTL)
    result = await db.execute(select(PriceCache).where(PriceCache.card_id == card_id))
    row = result.scalar_one_or_none()
    if row and row.fetched_at:
        cutoff = datetime.now(timezone.utc) - timedelta(seconds=PRICE_TTL_SECONDS)
        fetched_naive = row.fetched_at.replace(tzinfo=None)
        if fetched_naive > cutoff.replace(tzinfo=None):
            data = _row_to_dict(row)
            _memory_set(card_id, data)
            return data

    # 3. JustTCG API
    price_data = await _fetch_justtcg(card_id)

    # 4. Fallback: embedded TCGPlayer prices in card data
    if not price_data:
        price_data = await _extract_price_from_card_cache(card_id, db)

    if not price_data:
        return _row_to_dict(row) if row else None  # Return stale if nothing

    now = datetime.now(timezone.utc)
    if row:
        row.market_price = price_data.get("market_price")
        row.low_price = price_data.get("low_price")
        row.mid_price = price_data.get("mid_price")
        row.high_price = price_data.get("high_price")
        row.foil_market = price_data.get("foil_market")
        row.source = price_data.get("source", "unknown")
        row.fetched_at = now
    else:
        row = PriceCache(
            card_id=card_id,
            market_price=price_data.get("market_price"),
            low_price=price_data.get("low_price"),
            mid_price=price_data.get("mid_price"),
            high_price=price_data.get("high_price"),
            foil_market=price_data.get("foil_market"),
            source=price_data.get("source", "unknown"),
            fetched_at=now,
        )
        db.add(row)

    await db.commit()
    data = _row_to_dict(row)
    _memory_set(card_id, data)
    return data
