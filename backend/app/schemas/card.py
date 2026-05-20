from pydantic import BaseModel


class CardOut(BaseModel):
    card_id: str
    name: str
    set_id: str | None = None
    set_name: str | None = None
    series: str | None = None
    number: str | None = None
    rarity: str | None = None
    supertype: str | None = None
    subtypes: list[str] = []
    hp: int | None = None
    types: list[str] = []
    image_url_sm: str | None = None
    image_url_lg: str | None = None
    cached_at: str | None = None


class CardSearchResult(BaseModel):
    card_id: str
    name: str
    set_name: str | None = None
    number: str | None = None
    image_url_sm: str | None = None
    rarity: str | None = None


class CardSearchResponse(BaseModel):
    results: list[CardSearchResult]
    total: int


class PriceOut(BaseModel):
    card_id: str
    market_price: float | None = None
    low_price: float | None = None
    mid_price: float | None = None
    high_price: float | None = None
    foil_market: float | None = None
    source: str | None = None
    fetched_at: str | None = None


class SetOut(BaseModel):
    set_id: str
    name: str
    series: str | None = None
    total: int | None = None
    release_date: str | None = None
    symbol_url: str | None = None
    logo_url: str | None = None


class SetsResponse(BaseModel):
    sets: list[SetOut]
    total: int
