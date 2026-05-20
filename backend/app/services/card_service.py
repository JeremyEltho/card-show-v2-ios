"""
Fetches card data from pokemontcg.io and caches it in SQLite.
Cache TTL: 7 days. Falls back to DB if API is unavailable.
"""
import json
from datetime import datetime, timezone, timedelta
from typing import Any

import httpx
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, text

from app.models.card_cache import CardCache
from app.core.config import get_settings

settings = get_settings()

POKEMONTCG_BASE = "https://api.pokemontcg.io/v2"
CACHE_TTL_DAYS = 7

# In-memory short-lived cache to avoid DB reads on repeated identical requests
_memory_cache: dict[str, tuple[datetime, dict]] = {}
_MEMORY_TTL_SECONDS = 300


def _memory_get(key: str) -> dict | None:
    if key in _memory_cache:
        ts, val = _memory_cache[key]
        if datetime.now(timezone.utc) - ts < timedelta(seconds=_MEMORY_TTL_SECONDS):
            return val
        del _memory_cache[key]
    return None


def _memory_set(key: str, val: dict) -> None:
    _memory_cache[key] = (datetime.now(timezone.utc), val)


def _card_row_to_dict(row: CardCache) -> dict[str, Any]:
    return {
        "card_id": row.card_id,
        "name": row.name,
        "set_id": row.set_id,
        "set_name": row.set_name,
        "series": row.series,
        "number": row.number,
        "rarity": row.rarity,
        "supertype": row.supertype,
        "subtypes": json.loads(row.subtypes_json or "[]"),
        "hp": row.hp,
        "types": json.loads(row.types_json or "[]"),
        "image_url_sm": row.image_url_sm,
        "image_url_lg": row.image_url_lg,
        "cached_at": row.cached_at.isoformat(),
    }


def _api_card_to_row(card: dict) -> CardCache:
    images = card.get("images", {})
    set_data = card.get("set", {})
    return CardCache(
        card_id=card["id"],
        name=card["name"],
        set_id=set_data.get("id"),
        set_name=set_data.get("name"),
        series=set_data.get("series"),
        number=card.get("number"),
        rarity=card.get("rarity"),
        supertype=card.get("supertype"),
        subtypes_json=json.dumps(card.get("subtypes", [])),
        hp=int(card["hp"]) if card.get("hp") and str(card["hp"]).isdigit() else None,
        types_json=json.dumps(card.get("types", [])),
        image_url_sm=images.get("small"),
        image_url_lg=images.get("large"),
        data_json=json.dumps(card),
    )


async def _fetch_from_api(card_id: str) -> dict | None:
    headers = {}
    if settings.POKEMONTCG_API_KEY:
        headers["X-Api-Key"] = settings.POKEMONTCG_API_KEY
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            r = await client.get(f"{POKEMONTCG_BASE}/cards/{card_id}", headers=headers)
            if r.status_code == 200:
                return r.json().get("data")
    except httpx.HTTPError:
        pass
    return None


async def get_card(card_id: str, db: AsyncSession) -> dict | None:
    # 1. Memory cache
    cached = _memory_get(f"card:{card_id}")
    if cached:
        return cached

    # 2. DB cache (7-day TTL)
    result = await db.execute(select(CardCache).where(CardCache.card_id == card_id))
    row = result.scalar_one_or_none()
    if row:
        cutoff = datetime.now(timezone.utc) - timedelta(days=CACHE_TTL_DAYS)
        cached_naive = row.cached_at.replace(tzinfo=None) if row.cached_at else None
        if cached_naive and cached_naive > cutoff.replace(tzinfo=None):
            data = _card_row_to_dict(row)
            _memory_set(f"card:{card_id}", data)
            return data

    # 3. pokemontcg.io API
    api_card = await _fetch_from_api(card_id)
    if not api_card:
        # Return stale cache if API down
        return _card_row_to_dict(row) if row else None

    new_row = _api_card_to_row(api_card)

    # Upsert into DB
    if row:
        for attr in ["name", "set_id", "set_name", "series", "number", "rarity",
                     "supertype", "subtypes_json", "hp", "types_json",
                     "image_url_sm", "image_url_lg", "data_json"]:
            setattr(row, attr, getattr(new_row, attr))
        row.cached_at = datetime.now(timezone.utc)
    else:
        db.add(new_row)
        row = new_row

    await db.commit()

    # Update FTS
    await db.execute(
        text("INSERT OR REPLACE INTO card_fts(card_id, name) VALUES (:id, :name)"),
        {"id": new_row.card_id, "name": new_row.name},
    )
    await db.commit()

    data = _card_row_to_dict(row)
    _memory_set(f"card:{card_id}", data)
    return data


async def search_cards(query: str, set_id: str | None, limit: int, db: AsyncSession) -> list[dict]:
    """FTS5 search against cached cards; falls back to API if no local results."""
    if not query or len(query) < 2:
        return []

    # FTS5 search
    result = await db.execute(
        text("""
            SELECT c.card_id, c.name, c.set_id, c.set_name, c.number, c.image_url_sm, c.rarity
            FROM card_fts f
            JOIN card_cache c ON c.card_id = f.card_id
            WHERE card_fts MATCH :query
            LIMIT :limit
        """),
        {"query": f"{query}*", "limit": limit},
    )
    rows = result.fetchall()

    if not rows:
        # Fallback: search pokemontcg.io API directly
        rows_from_api = await _search_api(query, set_id, limit)
        for card in rows_from_api:
            r = _api_card_to_row(card)
            existing = await db.execute(select(CardCache).where(CardCache.card_id == r.card_id))
            if not existing.scalar_one_or_none():
                db.add(r)
        if rows_from_api:
            await db.commit()
            for card in rows_from_api:
                await db.execute(
                    text("INSERT OR REPLACE INTO card_fts(card_id, name) VALUES (:id, :name)"),
                    {"id": card["id"], "name": card["name"]},
                )
            await db.commit()
        return [
            {
                "card_id": c["id"],
                "name": c["name"],
                "set_name": c.get("set", {}).get("name"),
                "number": c.get("number"),
                "image_url_sm": c.get("images", {}).get("small"),
                "rarity": c.get("rarity"),
            }
            for c in rows_from_api
        ]

    return [
        {
            "card_id": r[0],
            "name": r[1],
            "set_id": r[2],
            "set_name": r[3],
            "number": r[4],
            "image_url_sm": r[5],
            "rarity": r[6],
        }
        for r in rows
    ]


async def _search_api(query: str, set_id: str | None, limit: int) -> list[dict]:
    headers = {}
    if settings.POKEMONTCG_API_KEY:
        headers["X-Api-Key"] = settings.POKEMONTCG_API_KEY
    q = f'name:"{query}*"'
    if set_id:
        q += f' set.id:{set_id}'
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            r = await client.get(
                f"{POKEMONTCG_BASE}/cards",
                params={"q": q, "pageSize": limit, "orderBy": "name"},
                headers=headers,
            )
            if r.status_code == 200:
                return r.json().get("data", [])
    except httpx.HTTPError:
        pass
    return []


async def get_all_sets(db: AsyncSession) -> list[dict]:
    """Fetch all sets from pokemontcg.io (cached in memory 24hrs)."""
    cached = _memory_get("sets:all")
    if cached:
        return cached

    headers = {}
    if settings.POKEMONTCG_API_KEY:
        headers["X-Api-Key"] = settings.POKEMONTCG_API_KEY
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            r = await client.get(
                f"{POKEMONTCG_BASE}/sets",
                params={"orderBy": "-releaseDate", "pageSize": 250},
                headers=headers,
            )
            if r.status_code == 200:
                sets = r.json().get("data", [])
                result = [
                    {
                        "set_id": s["id"],
                        "name": s["name"],
                        "series": s.get("series"),
                        "total": s.get("total"),
                        "release_date": s.get("releaseDate"),
                        "symbol_url": s.get("images", {}).get("symbol"),
                        "logo_url": s.get("images", {}).get("logo"),
                    }
                    for s in sets
                ]
                _memory_set("sets:all", result)
                return result
    except httpx.HTTPError:
        pass
    return []
