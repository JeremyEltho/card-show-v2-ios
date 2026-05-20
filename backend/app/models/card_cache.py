from datetime import datetime, timezone
from sqlalchemy import String, DateTime, Integer, Float, Text
from sqlalchemy.orm import Mapped, mapped_column
from app.core.database import Base


class CardCache(Base):
    __tablename__ = "card_cache"

    card_id: Mapped[str] = mapped_column(String, primary_key=True)
    name: Mapped[str] = mapped_column(String, nullable=False, index=True)
    set_id: Mapped[str | None] = mapped_column(String)
    set_name: Mapped[str | None] = mapped_column(String)
    series: Mapped[str | None] = mapped_column(String)
    number: Mapped[str | None] = mapped_column(String)
    rarity: Mapped[str | None] = mapped_column(String)
    supertype: Mapped[str | None] = mapped_column(String)
    subtypes_json: Mapped[str | None] = mapped_column(Text)
    hp: Mapped[int | None] = mapped_column(Integer)
    types_json: Mapped[str | None] = mapped_column(Text)
    image_url_sm: Mapped[str | None] = mapped_column(String)
    image_url_lg: Mapped[str | None] = mapped_column(String)
    data_json: Mapped[str] = mapped_column(Text, nullable=False)
    cached_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )


class PriceCache(Base):
    __tablename__ = "price_cache"

    card_id: Mapped[str] = mapped_column(String, primary_key=True)
    market_price: Mapped[float | None] = mapped_column(Float)
    low_price: Mapped[float | None] = mapped_column(Float)
    mid_price: Mapped[float | None] = mapped_column(Float)
    high_price: Mapped[float | None] = mapped_column(Float)
    foil_market: Mapped[float | None] = mapped_column(Float)
    source: Mapped[str] = mapped_column(String, default="justtcg")
    fetched_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
