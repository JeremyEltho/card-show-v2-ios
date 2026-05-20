from datetime import datetime, timezone, timedelta, date

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_

from app.models.inventory import InventoryItem, Transaction
from app.models.card_cache import CardCache, PriceCache


async def get_summary(user_id: str, db: AsyncSession) -> dict:
    # All non-deleted items
    all_items = (await db.execute(
        select(InventoryItem).where(
            InventoryItem.user_id == user_id,
            InventoryItem.deleted_at.is_(None),
        )
    )).scalars().all()

    total_invested = 0.0
    total_revenue = 0.0
    unrealized_gain = 0.0
    portfolio_value = 0.0
    cards_holding = 0
    cards_sold = 0
    top_card = None
    best_gain_pct = None

    for item in all_items:
        price_row = await db.get(PriceCache, item.card_id)
        market = price_row.market_price if price_row else None
        card_row = await db.get(CardCache, item.card_id)

        if item.status in ("holding", "bought"):
            cards_holding += 1
            if item.purchase_price:
                total_invested += item.purchase_price * item.quantity
            if market:
                portfolio_value += market * item.quantity
                if item.purchase_price:
                    gain = (market - item.purchase_price) * item.quantity
                    unrealized_gain += gain
                    gain_pct = (market - item.purchase_price) / item.purchase_price * 100
                    if best_gain_pct is None or gain_pct > best_gain_pct:
                        best_gain_pct = gain_pct
                        top_card = {
                            "card_id": item.card_id,
                            "name": card_row.name if card_row else None,
                            "gain_pct": round(gain_pct, 1),
                        }
        elif item.status == "sold":
            cards_sold += 1
            if item.sale_price:
                total_revenue += item.sale_price * item.quantity
            if item.purchase_price:
                total_invested += item.purchase_price * item.quantity

    net_profit = round(total_revenue - total_invested, 2)

    # Today's show summary (transactions created today)
    today_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    today_txs = (await db.execute(
        select(Transaction).where(
            Transaction.user_id == user_id,
            Transaction.created_at >= today_start.replace(tzinfo=None),
        )
    )).scalars().all()

    today_spent = sum(t.price * t.quantity for t in today_txs if t.type in ("purchase", "trade_in"))
    today_earned = sum(t.price * t.quantity for t in today_txs if t.type in ("sale", "trade_out"))
    today_cards = len(today_txs)

    return {
        "total_cards": len(all_items),
        "total_invested": round(total_invested, 2),
        "total_revenue": round(total_revenue, 2),
        "net_profit": net_profit,
        "unrealized_gain": round(unrealized_gain, 2),
        "portfolio_value": round(portfolio_value, 2),
        "cards_holding": cards_holding,
        "cards_sold": cards_sold,
        "top_gainer": top_card,
        "show_summary": {
            "cards_logged": today_cards,
            "spent": round(today_spent, 2),
            "earned": round(today_earned, 2),
            "net": round(today_earned - today_spent, 2),
        },
    }


async def get_history(
    user_id: str,
    from_date: date,
    to_date: date,
    granularity: str,
    db: AsyncSession,
) -> dict:
    txs = (await db.execute(
        select(Transaction).where(
            Transaction.user_id == user_id,
            Transaction.created_at >= datetime.combine(from_date, datetime.min.time()),
            Transaction.created_at <= datetime.combine(to_date, datetime.max.time()),
        ).order_by(Transaction.created_at)
    )).scalars().all()

    # Group by date granularity
    buckets: dict[str, dict] = {}
    for tx in txs:
        dt = tx.created_at
        if granularity == "month":
            key = f"{dt.year}-{dt.month:02d}"
        elif granularity == "week":
            week = dt.isocalendar()[1]
            key = f"{dt.year}-W{week:02d}"
        else:
            key = dt.strftime("%Y-%m-%d")

        if key not in buckets:
            buckets[key] = {"date": key, "revenue": 0.0, "cost": 0.0, "net": 0.0, "volume": 0}

        if tx.type in ("sale", "trade_out"):
            buckets[key]["revenue"] += tx.price * tx.quantity
        else:
            buckets[key]["cost"] += tx.price * tx.quantity
        buckets[key]["volume"] += 1

    series = []
    for k, v in sorted(buckets.items()):
        v["net"] = round(v["revenue"] - v["cost"], 2)
        v["revenue"] = round(v["revenue"], 2)
        v["cost"] = round(v["cost"], 2)
        series.append(v)

    return {
        "period": {"from": str(from_date), "to": str(to_date)},
        "granularity": granularity,
        "series": series,
    }
