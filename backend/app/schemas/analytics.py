from pydantic import BaseModel


class ShowSummary(BaseModel):
    cards_logged: int
    spent: float
    earned: float
    net: float


class TopCard(BaseModel):
    card_id: str
    name: str | None = None
    gain_pct: float | None = None


class AnalyticsSummary(BaseModel):
    total_cards: int
    total_invested: float
    total_revenue: float
    net_profit: float
    unrealized_gain: float
    portfolio_value: float
    cards_holding: int
    cards_sold: int
    top_gainer: TopCard | None = None
    show_summary: ShowSummary


class HistoryPoint(BaseModel):
    date: str
    revenue: float
    cost: float
    net: float
    volume: int


class AnalyticsHistory(BaseModel):
    period: dict
    granularity: str
    series: list[HistoryPoint]
